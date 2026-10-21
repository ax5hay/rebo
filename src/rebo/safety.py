"""SQL guard: parse, prove read-only, validate every table and column, cap rows.

Works on the parsed syntax tree (sqlglot), never on regexes over text. The database
user should still be read-only; this is the second wall, not the only one.
See docs/06-sql-safety.md.
"""
from __future__ import annotations

import hashlib
from contextvars import ContextVar
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


# ---- the query in plain steps (shown under every report) ------------------------------------------
# Research on people checking text-to-SQL answers (Berant et al. 2018; DIY, IUI 2021; SQLucid) found
# that non-experts judge correctness far better from a step-by-step, plain-language reading of the
# query than from SQL. These steps are generated from the syntax tree, never by a model, so they say
# exactly what the query does.

# alias -> table, and the main table, of the query being explained (per call: safe across threads/tasks)
_EXPLAIN: ContextVar[tuple[dict[str, str], str]] = ContextVar("rebo_explain", default=({}, ""))


def _words(node) -> str:
    """A column or expression in plain words: c.full_name -> "full name"; columns of joined tables
    carry their table ("building name"), so "name" or "id" is never ambiguous."""
    if isinstance(node, exp.Column):
        tables, main = _EXPLAIN.get()
        table = tables.get(node.table.lower(), node.table) if node.table else ""
        col = node.name.replace("_", " ")
        if table and table != main and not col.startswith(table.replace("_", " ")):
            return f"{table.replace('_', ' ')} {col}"
        return col
    if isinstance(node, exp.Literal):
        return f"'{node.this}'" if node.is_string else node.this
    if isinstance(node, exp.Alias):
        return _words(node.this)
    if isinstance(node, exp.Count):
        inner = node.this
        what = "rows" if isinstance(inner, exp.Star) or inner is None else _words(inner)
        return f"number of {'different ' if node.args.get('distinct') or isinstance(inner, exp.Distinct) else ''}{what}"
    agg = {exp.Sum: "total", exp.Avg: "average", exp.Min: "lowest", exp.Max: "highest"}
    for kind, word in agg.items():
        if isinstance(node, kind):
            return f"{word} {_words(node.this)}"
    if isinstance(node, (exp.Tuple, exp.Array)):
        return ", ".join(_words(e) for e in node.expressions)
    return node.sql()


def _condition(node) -> list[str]:
    """One condition in words; AND is split into separate lines."""
    if isinstance(node, exp.And):
        return _condition(node.this) + _condition(node.expression)
    if isinstance(node, exp.Paren):
        return _condition(node.this)
    ops = {exp.EQ: "is", exp.NEQ: "is not", exp.GT: "is more than", exp.GTE: "is at least",
           exp.LT: "is less than", exp.LTE: "is at most"}
    for kind, word in ops.items():
        if isinstance(node, kind):
            return [f"{_words(node.this)} {word} {_words(node.expression)}"]
    if isinstance(node, exp.Is):
        return [f"{_words(node.this)} is empty"]
    if isinstance(node, exp.Not) and isinstance(node.this, exp.Is):
        return [f"{_words(node.this.this)} is not empty"]
    if isinstance(node, exp.In):
        return [f"{_words(node.this)} is one of {', '.join(_words(e) for e in node.expressions)}"]
    if isinstance(node, exp.Like):
        verb = "does not match" if node.args.get("negate") else "matches"
        return [f"{_words(node.this)} {verb} {_words(node.expression)}"]
    if isinstance(node, exp.Between):
        return [f"{_words(node.this)} is between {_words(node.args['low'])} and {_words(node.args['high'])}"]
    if isinstance(node, exp.Or):
        return [" or ".join(" and ".join(_condition(p)) for p in (node.this, node.expression))]
    if isinstance(node, exp.Exists):
        return ["a matching row exists in a related table"]
    if isinstance(node, exp.Not) and isinstance(node.this, exp.Exists):
        return ["no matching row exists in a related table"]
    return [node.sql()]


def explain_sql(sql: str, dialect: str) -> list[str]:
    """The query as numbered plain-language steps; [] when it cannot be read (the SQL is still shown)."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return []
    if not isinstance(tree, exp.Select) or not tree.args.get("from_"):
        return []
    src = tree.args["from_"].this
    tables = {t.alias_or_name.lower(): t.name for t in [src, *(j.this for j in tree.args.get("joins") or [])]
              if isinstance(t, exp.Table)}
    token = _EXPLAIN.set((tables, src.name if isinstance(src, exp.Table) else ""))
    try:
        return _explain_steps(tree, src)
    finally:
        _EXPLAIN.reset(token)


def _explain_steps(tree, src) -> list[str]:
    steps = []
    with_ = tree.args.get("with_")
    if with_:
        steps.append(f"Prepare {len(with_.expressions)} intermediate result{'s' if len(with_.expressions) > 1 else ''} first")
    look = f"Look in {src.name.replace('_', ' ') if isinstance(src, exp.Table) else 'a sub-result'}"
    joins = []
    for j in tree.args.get("joins") or []:
        name = j.this.name.replace("_", " ") if isinstance(j.this, exp.Table) else "a sub-result"
        joins.append(f"{name}{' where there is one' if (j.side or '').upper() == 'LEFT' else ''}")
    steps.append(look + (", with the matching " + ", ".join(joins) if joins else ""))
    where = tree.args.get("where")
    if where is not None:
        steps.append("Keep rows where " + "; and ".join(_condition(where.this)))
    group = tree.args.get("group")
    if group:
        steps.append("Combine rows per " + ", ".join(_words(g) for g in group.expressions))
    having = tree.args.get("having")
    if having is not None:
        steps.append("Keep groups where " + "; and ".join(_condition(having.this)))
    shown = [p.alias or _words(p) if isinstance(p, exp.Alias) else _words(p) for p in tree.expressions]
    steps.append(("Show different " if tree.args.get("distinct") else "Show ") + ", ".join(
        s.replace("_", " ") for s in shown))
    order = tree.args.get("order")
    if order:
        parts = []
        for o in order.expressions:
            key = o.this
            if isinstance(key, exp.Literal) and not key.is_string and key.this.isdigit() and int(key.this) <= len(shown):
                name = shown[int(key.this) - 1].replace("_", " ")
            else:
                name = _words(key)
            parts.append(f"{name}{' (highest first)' if o.args.get('desc') else ''}")
        steps.append("Sort by " + ", ".join(parts))
    limit = tree.args.get("limit")
    if limit is not None and isinstance(limit.expression, exp.Literal):
        steps.append(f"Only the first {limit.expression.this}")
    return steps


# ---- query skeletons (B-050) -------------------------------------------------------------------
# What a query does, without its literal values: which tables, which columns, which clauses and which
# predicate shapes. Two queries that answer the same kind of question share most of it even when their
# values, aliases and column order differ (DAIL-SQL and UCS-SQL select examples by such skeletons).
_SKELETON_WEIGHT = {"T": 3.0, "P": 2.0, "C": 1.0, "N": 1.0}
_STRUCTURE = (exp.Join, exp.Where, exp.Group, exp.Having, exp.Order, exp.Limit, exp.Distinct, exp.Subquery, exp.Union,
              exp.Case, exp.Window, exp.Count, exp.Sum, exp.Avg, exp.Max, exp.Min)
_PREDICATES = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Like, exp.ILike, exp.In, exp.Between, exp.Is)


def skeleton(sql: str, dialect: str) -> dict[str, float]:
    """Weighted features of a query's shape: T:table, C:column, N:clause or aggregate, P:column+operator.
    Empty when the SQL does not parse."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except ParseError:
        return {}
    feats: set[str] = set()
    feats.update(f"T:{t.name.lower()}" for t in tree.find_all(exp.Table) if t.name)
    feats.update(f"C:{c.name.lower()}" for c in tree.find_all(exp.Column) if c.name)
    for node in tree.find_all(*_STRUCTURE):
        side = f":{node.side.lower()}" if isinstance(node, exp.Join) and node.side else ""
        feats.add(f"N:{type(node).__name__.lower()}{side}")
    for p in tree.find_all(*_PREDICATES):
        col = p.this if isinstance(p.this, exp.Column) else next(p.find_all(exp.Column), None)
        if col is not None:
            feats.add(f"P:{col.name.lower()}:{type(p).__name__.lower()}")
    return {f: _SKELETON_WEIGHT[f[0]] for f in feats}


def skeleton_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Weighted Jaccard of two skeletons, 0..1."""
    keys = a.keys() | b.keys()
    top = sum(min(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    bottom = sum(max(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    return top / bottom if bottom else 0.0


def join_edges(sql: str, dialect: str) -> list[tuple[str, str, str, str]]:
    """Join conditions of a query as (table, column, table, column), aliases resolved to table names and
    each pair in a fixed order: the joins a confirmed report proves (B-055). Only column = column
    conditions between two different tables; anything else (literals, functions) is not a join path."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except ParseError:
        return []
    out: set[tuple[str, str, str, str]] = set()
    for sel in tree.find_all(exp.Select):
        if not sel.args.get("from_"):
            continue
        sources = [sel.args["from_"].this, *(j.this for j in sel.args.get("joins") or [])]
        aliases = {t.alias_or_name.lower(): t.name.lower() for t in sources if isinstance(t, exp.Table)}
        for j in sel.args.get("joins") or []:
            on = j.args.get("on")
            for eq in (on.find_all(exp.EQ) if on is not None else []):
                a, b = eq.left, eq.right
                if not (isinstance(a, exp.Column) and isinstance(b, exp.Column) and a.table and b.table):
                    continue
                ta, tb = aliases.get(a.table.lower()), aliases.get(b.table.lower())
                if ta and tb and ta != tb:
                    l, r = sorted([(ta, a.name.lower()), (tb, b.name.lower())])
                    out.add((l[0], l[1], r[0], r[1]))
    return sorted(out)


def fanout_probes(sql: str, dialect: str) -> list[tuple[str, str]]:
    """Metamorphic fan-out check (B-057). For each joined table that contributes no column to the query
    (it appears only in its own ON condition), the same query with that join rewritten as an EXISTS
    filter. If the two return different rows, the join was multiplying them: rows repeat or sums grow.
    Returns (table, rewritten SQL) pairs; empty when nothing qualifies or the SQL does not parse."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except ParseError:
        return []
    if not isinstance(tree, exp.Select) or not tree.args.get("joins"):
        return []
    # COUNT(*) / COUNT(1) counts the joined rows on purpose ("buildings with more than 10 units")
    if any(isinstance(c.this, (exp.Star, exp.Literal)) for c in tree.find_all(exp.Count)):
        return []
    out = []
    for i, j in enumerate(tree.args["joins"]):
        t, on = j.this, j.args.get("on")
        if not isinstance(t, exp.Table) or on is None or isinstance(on, exp.Boolean) or j.args.get("using"):
            continue
        alias = t.alias_or_name.lower()
        rest = tree.copy()
        rest.args["joins"][i].pop()
        if any(c.table.lower() == alias for c in rest.find_all(exp.Column) if c.table):
            continue  # its columns are used: not a pure multiplier
        if (j.side or "").upper() == "LEFT":
            rewritten = rest  # an unused LEFT JOIN can only add duplicates
        else:
            sub = exp.select("1").from_(t.copy()).where(on.copy())
            rewritten = rest.where(exp.Exists(this=sub))
        out.append((t.name, rewritten.sql(dialect=dialect)))
    return out
