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
