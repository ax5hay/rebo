"""SQL guard: parse, prove read-only, validate every table and column, cap rows.

Works on the parsed syntax tree (sqlglot), never on regexes over text. The database
user should still be read-only; this is the second wall, not the only one.
See docs/06-sql-safety.md.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.errors import OptimizeError, ParseError
from sqlglot.optimizer.qualify import qualify

# Node types that can change data, schema, session or server state.
_FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
    exp.Command, exp.Into, exp.Lock, exp.Set, exp.Transaction, exp.Commit, exp.Rollback,
    exp.Use, exp.Show, exp.Describe, exp.Pragma, exp.Copy, exp.LoadData, exp.Grant,
)
# Functions that stall the server, read files or reach outside the database.
_FORBIDDEN_FUNCS = {
    "sleep", "benchmark", "load_file", "get_lock", "release_lock", "pg_sleep", "dblink",
    "lo_import", "lo_export", "pg_read_file", "xp_cmdshell", "sys_exec", "sys_eval",
}
_DIALECTS = {"postgresql": "postgres", "mssql": "tsql", "mysql": "mysql", "mariadb": "mysql",
             "sqlite": "sqlite", "snowflake": "snowflake", "bigquery": "bigquery",
             "oracle": "oracle", "duckdb": "duckdb", "redshift": "redshift"}


def sqlglot_dialect(sqlalchemy_dialect: str) -> str:
    return _DIALECTS.get(sqlalchemy_dialect, sqlalchemy_dialect)


class GuardError(ValueError):
    """Rejected SQL. The message is written for the agent to act on."""


@dataclass
class Guarded:
    sql: str                      # what will actually run (row cap applied)
    tables: set[str] = field(default_factory=set)
    columns: set[tuple[str, str]] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)


def _forbidden_function(node: exp.Expression) -> str | None:
    if isinstance(node, exp.Anonymous):
        name = str(node.this).lower()
    elif isinstance(node, exp.Func):
        name = node.sql_name().lower()
    else:
        return None
    return name if name in _FORBIDDEN_FUNCS else None


def _cte_names(root: exp.Expression) -> set[str]:
    return {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}


def _apply_limit(root: exp.Query, cap: int) -> exp.Query:
    """Cap rows at `cap` (keeps a smaller LIMIT the author wrote)."""
    current = root.args.get("limit")
    if current is not None:
        try:
            if int(current.expression.name) <= cap:
                return root
        except (AttributeError, ValueError):
            pass
    return root.limit(cap, copy=False)


def guard(
    sql: str,
    *,
    dialect: str,
    schema: dict[str, dict[str, str]],
    sensitive: set[tuple[str, str]] | None = None,
    allowed_tables: set[str] | None = None,
    row_cap: int,
) -> Guarded:
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise GuardError("Empty SQL.")
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except ParseError as e:
        raise GuardError(f"SQL does not parse: {e.errors[0]['description'] if e.errors else e}") from e
    if len(statements) != 1:
        raise GuardError("Send exactly one SELECT statement.")
    root = statements[0]
    if not isinstance(root, (exp.Select, exp.SetOperation)):
        raise GuardError(f"Only SELECT queries are allowed (got {root.key.upper()}).")
    for node in root.walk():
        if isinstance(node, _FORBIDDEN):
            raise GuardError(f"{node.key.upper()} is not allowed in a report query.")
        if (fn := _forbidden_function(node)):
            raise GuardError(f"Function {fn.upper()} is not allowed.")

    known = {t.lower(): t for t in schema}
    ctes = _cte_names(root)
    tables: set[str] = set()
    for t in root.find_all(exp.Table):
        name = t.name.lower()
        if not name or name in ctes:
            continue
        if name not in known:
            raise GuardError(f"Table '{t.name}' does not exist. Use search_schema to find the right table.")
        real = known[name]
        if allowed_tables is not None and real not in allowed_tables:
            raise GuardError(f"Table '{real}' is not available for reports.")
        tables.add(real)

    result = Guarded(sql="", tables=tables)
    lowered = {t.lower(): {c.lower(): ty for c, ty in cols.items()} for t, cols in schema.items()}
    try:
        qualified = qualify(root.copy(), schema=lowered, dialect=dialect,
                            validate_qualify_columns=True, quote_identifiers=False, identify=False)
    except OptimizeError as e:
        msg = str(e)
        if "could not be resolved" in msg or "Unknown column" in msg or "Ambiguous" in msg:
            raise GuardError(f"{msg.split('. Line')[0]}. Check the columns with describe_table.") from e
        qualified = None
        result.warnings.append(f"column check skipped: {msg[:160]}")
    except Exception as e:  # sqlglot cannot model every dialect feature; the DB still validates
        qualified = None
        result.warnings.append(f"column check skipped: {type(e).__name__}")

    if qualified is not None:
        alias_to_table = {}
        for t in qualified.find_all(exp.Table):
            if t.name.lower() in known:
                alias_to_table[t.alias_or_name.lower()] = known[t.name.lower()]
        for c in qualified.find_all(exp.Column):
            table = alias_to_table.get((c.table or "").lower())
            if table:
                real_col = next((k for k in schema[table] if k.lower() == c.name.lower()), c.name)
                result.columns.add((table, real_col))
        blocked = sorted(f"{t}.{c}" for t, c in result.columns if (t, c) in (sensitive or set()))
        if blocked:
            raise GuardError(f"Column(s) {', '.join(blocked)} hold protected data and cannot be used.")

    # SELECT * would return protected columns the check above saw only after expansion,
    # so a starred query runs in its expanded (qualified) form.
    has_star = any(p.is_star for sel in root.find_all(exp.Select) for p in sel.expressions)
    runnable = qualified if (has_star and qualified is not None) else root
    runnable = _apply_limit(runnable, row_cap)
    result.sql = runnable.sql(dialect=dialect, pretty=True)
    return result


def canonical_hash(sql: str, dialect: str) -> str:
    """Same query, different formatting/limit -> same hash. Used to recognise repeat confirmations."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
        tree.set("limit", None)
        text = tree.sql(dialect=dialect, normalize=True, comments=False)
    except Exception:
        text = " ".join(sql.lower().split())
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def tables_in(sql: str, dialect: str) -> list[str]:
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return []
    ctes = _cte_names(tree)
    return sorted({t.name for t in tree.find_all(exp.Table) if t.name and t.name.lower() not in ctes})


def parameterize(sql: str, dialect: str) -> tuple[str, list[str | int | float]] | None:
    """Replace the literals of a query with :p1..:pN placeholders (LIMIT/OFFSET and type sizes stay).
    Returns (template, values in placeholder order), or None when the SQL cannot be parsed."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return None
    values: list[str | int | float] = []
    for lit in [n for n in tree.dfs() if isinstance(n, exp.Literal)]:
        if lit.find_ancestor(exp.Limit, exp.Offset, exp.DataType):
            continue
        if lit.is_string:
            values.append(lit.this)
        else:
            values.append(float(lit.this) if any(ch in lit.this for ch in ".eE") else int(lit.this))
        lit.replace(exp.Placeholder(this=f"p{len(values)}"))
    return tree.sql(dialect=dialect), values


def fill_params(template: str, dialect: str, values: list[str | int | float]) -> str:
    """Put values back into a template from `parameterize` as syntax-tree literals (never by string
    interpolation, so a value can never change the shape of the query)."""
    tree = sqlglot.parse_one(template, read=dialect)
    for ph in list(tree.find_all(exp.Placeholder)):
        name = str(ph.this or "")
        if not name.startswith("p") or not name[1:].isdigit() or not 1 <= int(name[1:]) <= len(values):
            raise ValueError(f"unknown placeholder :{name}")
        v = values[int(name[1:]) - 1]
        ph.replace(exp.Literal.number(v) if isinstance(v, (int, float)) and not isinstance(v, bool)
                   else exp.Literal.string(str(v)))
    return tree.sql(dialect=dialect)


def drill_sql(sql: str, dialect: str, columns: list[str], row: list, schema: dict[str, dict[str, str]],
              sensitive: set[tuple[str, str]] | None = None) -> tuple[str, list[tuple[str, object]]]:
    """Detail query behind one row of a grouped report: GROUP BY/HAVING/aggregates removed, each group
    value added as a filter, and the readable (non-protected) columns of the first FROM table selected.
    Returns (sql, [(group label, value)]). Raises ValueError when the report is not a simple grouped SELECT."""
    tree = sqlglot.parse_one(sql, read=dialect)
    group = tree.args.get("group") if isinstance(tree, exp.Select) else None
    source = tree.args.get("from_").this if isinstance(tree, exp.Select) and tree.args.get("from_") else None
    if not group or not isinstance(source, exp.Table):
        raise ValueError("Only summary reports (grouped by something) can be drilled into.")
    table = next((t for t in schema if t.lower() == source.name.lower()), None)
    if table is None:
        raise ValueError("The report's main table is not in the catalog.")
    filters, labels = [], []
    for g in group.expressions:
        idx = None
        for i, p in enumerate(tree.expressions):
            inner = p.this if isinstance(p, exp.Alias) else p
            if inner == g or (isinstance(g, exp.Column) and not g.table and p.alias_or_name == g.name):
                idx = i
                break
        if idx is None and isinstance(g, exp.Literal) and not g.is_string and int(g.this) - 1 < len(tree.expressions):
            idx = int(g.this) - 1  # GROUP BY 1
        if idx is None or idx >= len(row):
            raise ValueError("A grouping of this report is not among its columns, so the cell cannot be traced.")
        expr = tree.expressions[idx]
        expr = expr.this if isinstance(expr, exp.Alias) else expr
        value = row[idx]
        if value is None:
            filters.append(exp.Is(this=expr.copy(), expression=exp.Null()))
        else:
            lit = (exp.Literal.number(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
                   else exp.Literal.string(str(value)))
            filters.append(exp.EQ(this=expr.copy(), expression=lit))
        labels.append((columns[idx] if idx < len(columns) else expr.sql(dialect=dialect), value))
    alias = source.alias_or_name
    cols = [exp.column(c, table=alias) for c in schema[table] if (table, c) not in (sensitive or set())]
    detail = tree.copy()
    detail.set("expressions", cols)
    for key in ("group", "having", "order", "limit", "distinct"):
        detail.set(key, None)
    detail = detail.where(exp.and_(*filters), copy=False)
    return detail.sql(dialect=dialect), labels
