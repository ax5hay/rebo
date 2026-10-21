"""The agent loop: one Pydantic AI agent, six tools, three typed outcomes.

The model explores (search schema / values / knowledge, describe tables, find joins,
probe with small queries) and ends the turn with exactly one of:
  Report   final SQL + title + plain-language assumptions (+ things worth remembering)
  Clarify  one question with 2-4 concrete options, only when the evidence disagrees
  Reply    plain answer for anything that is not a report request

A Report is only accepted after the output validator has run its SQL through the guard
and the database; failures go back to the model as a retry. See docs/03-agent-loop.md.
"""
from __future__ import annotations

import re

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal

import sqlglot
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, PromptedOutput, RunContext, ToolOutput
from pydantic_ai.models import Model
from sqlglot import exp

from .safety import GuardError, guard
from .target import QueryResult

if TYPE_CHECKING:
    from .knowledge import User
    from .service import App


# ---- outcomes -------------------------------------------------------------------------
class Learnable(BaseModel):
    """Something the user stated that should shape future answers."""
    kind: Literal["term", "note", "join"] = Field(description=(
        "term = meaning of a business word; note = a rule or fact; join = how two tables connect"))
    title: str = Field(description="Short name, e.g. 'active client' or 'case to contact'")
    body: str = Field(description="The meaning or rule in plain words, as the user stated it")
    sql: str | None = Field(None, description=(
        "term: the SQL predicate that implements it, e.g. \"orders.status = 'shipped'\"; "
        "join: \"table_a.col = table_b.col\"; note: usually empty"))


class Report(BaseModel):
    """A finished report."""
    title: str = Field(description="Short report title in business words")
    sql: str = Field(description="One read-only SELECT. Readable column aliases. No LIMIT needed.")
    assumptions: list[str] = Field(description=(
        "Every interpretation you made, in plain business words, no table or column names"))
    used_knowledge: list[str] = Field(default_factory=list, description="ids of learned items you relied on")
    learnable: list[Learnable] = Field(default_factory=list, description=(
        "Only facts the user explicitly stated this conversation that will apply to future questions"))
    follow_ups: list[str] = Field(default_factory=list, max_length=3, description=(
        "Up to 3 short next questions that drill into this result (by a dimension, a time range, a segment)"))


class Question(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=4, description="Concrete, mutually exclusive readings")
    option_sql: list[str] = Field(default_factory=list, max_length=4, description=(
        "The report SELECT for each option, same order (at least the first two). If they return the same "
        "rows the bot answers instead of asking."))


class Clarify(BaseModel):
    """Ask before running, because reasonable readings give materially different answers.
    All open questions go into ONE clarify turn, so the user answers once."""
    questions: list[Question] = Field(min_length=1, max_length=3)
    why: str = Field(description="One sentence: what differs between the readings")


class Reply(BaseModel):
    """A plain answer when the message is not a report request."""
    text: str
    used_knowledge: list[str] = Field(default_factory=list, description=(
        "ids of learned items the answer relies on (e.g. when asked what a word means); shown as sources"))
    learnable: list[Learnable] = Field(default_factory=list)


Outcome = Report | Clarify | Reply


class Trace(list):
    """The turn's tool trace. `on_append` (optional) sees each step as it happens: streaming progress."""

    def __init__(self, items=(), on_append: Callable[[dict[str, Any]], None] | None = None):
        super().__init__(items)
        self.on_append = on_append

    def append(self, step: dict[str, Any]) -> None:
        super().append(step)
        if self.on_append:
            self.on_append(step)


@dataclass
class Deps:
    app: "App"
    user: "User"
    trace: list[dict[str, Any]] = field(default_factory=Trace)
    final: QueryResult | None = None
    final_sql: str | None = None
    zero_row_retry: bool = False
    grain_retry: bool = False
    trap_retry: bool = False
    shape_retry: bool = False
    shown: set[str] = field(default_factory=set)  # knowledge ids already in the agent's context
    probes: int = 0


INSTRUCTIONS = """\
You build database reports for business users who do not know SQL or the schema.

How to work
0. <my_defaults> are this user's standing preferences (e.g. a date range or a place). Apply each one unless the
   question says otherwise, and state every default you applied as an assumption.
1. Read <learned_knowledge> first. Items marked "verified" were checked by an admin; items marked
   "yours" were taught by this user and apply to them. When a saved example answers the same kind of
   question, adapt it (change only literal values, dates, grouping) instead of starting over, and list
   its id in used_knowledge. When a learned term defines a word the user used, follow it exactly.
2. Find tables with search_schema, inspect them with describe_table. Never guess a table or column.
3. Map every literal the user mentions (statuses, stages, types, names, places) to stored values with
   search_values or the values shown by describe_table. Match stored spelling and case exactly.
4. Get join conditions from describe_table or find_join_path. Prefer declared and learned joins.
   Watch for fan-out: joining a one-to-many table multiplies rows; use DISTINCT or aggregate when needed.
5. Use run_sql for small checks (distinct values, counts, a few sample rows). Keep it under 8 probes.
6. Finish with exactly one outcome:
   - Report: the final SELECT. Select readable columns (names, labels, dates), not only ids. Give every
     column a readable alias. Never select columns marked protected. No LIMIT needed. The SQL is executed
     before it is shown; errors come back to you.
   - Clarify: only when two or more readings are plausible, learned knowledge does not settle it, and the
     readings give materially different results. Put EVERY open question into this one clarify (at most 3),
     each with 2-4 concrete options taken from stored values where possible, so the user answers once.
     If one reading is clearly the most likely, do not ask: answer with it and state it as an assumption.
     Give option_sql for each question: the report SQL for its first two options (or all of them).
     Never ask again about something the user already answered in this conversation.
   - Reply: when the message is not asking for data.
7. assumptions: every interpretation you made, in plain business language. No table or column names.
8. follow_ups: up to 3 short next questions a person would ask about this result (drill down by a
   dimension, narrow the time range, compare segments). They are offered as one-click buttons.
9. learnable: only what the user explicitly stated as a definition, rule or correction that should apply
   to future questions. Never add your own guesses. Empty in most turns.

When the user corrects a previous report, their correction is the authority: revise the report, and put the
general rule behind the correction in learnable.
"""


def entity_key(sql: str, dialect: str, pks: dict[str, list[str]]) -> tuple[int, str] | None:
    """(result column index, table) of the first projected column that is the single-column primary
    key of a FROM/JOIN table, for a top-level SELECT with joins and no GROUP BY; otherwise None."""
    try:
        sel = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.ParseError:
        return None
    if not isinstance(sel, exp.Select) or not sel.args.get("joins") or sel.args.get("group"):
        return None
    sources = [sel.args["from_"].this, *(j.this for j in sel.args["joins"])] if sel.args.get("from_") else []
    tables = {(t.alias_or_name).lower(): t.name for t in sources if isinstance(t, exp.Table)}
    pk = {t.lower(): cols[0] for t, cols in pks.items() if len(cols) == 1}
    for i, p in enumerate(sel.expressions):
        col = p.this if isinstance(p, exp.Alias) else p
        if isinstance(col, exp.Star) or isinstance(col, exp.Column) and isinstance(col.this, exp.Star):
            return None
        if not isinstance(col, exp.Column):
            continue
        if col.table:
            owners = [tables[col.table.lower()]] if col.table.lower() in tables else []
        else:
            owners = [t for t in tables.values() if pk.get(t.lower(), "").lower() == col.name.lower()]
        if len(owners) == 1 and pk.get(owners[0].lower(), "").lower() == col.name.lower():
            return i, owners[0]
    return None


def sql_trap(sql: str, dialect: str, pks: dict[str, list[str]]) -> str | None:
    """A query that runs but very likely answers a different question (research basis: doc 16 §5). Checks,
    on the syntax tree only: comparison with NULL; NOT IN over a subquery (one NULL empties the result);
    a LEFT JOIN undone by a WHERE filter on the joined table; SUM/AVG of a column repeated by a
    one-to-many join; a join with no condition at all (a cartesian product). Returns what is wrong in words, or None."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.ParseError:
        return None
    for cmp in tree.find_all(exp.EQ, exp.NEQ):
        if isinstance(cmp.left, exp.Null) or isinstance(cmp.right, exp.Null):
            return "it compares with NULL using = or <>, which is never true. Use IS NULL / IS NOT NULL."
    for n in tree.find_all(exp.Not):
        if isinstance(n.this, exp.In) and n.this.args.get("query"):
            return ("it uses NOT IN with a subquery: if the subquery returns any NULL, no rows match. Use NOT EXISTS, "
                    "or filter the subquery with IS NOT NULL.")
    for sel in tree.find_all(exp.Select):
        joins = sel.args.get("joins") or []
        where = sel.args.get("where")
        for j in joins:  # every row times every row: almost never meant, and can run for very long (B-058)
            on = j.args.get("on")
            no_condition = (on is None or isinstance(on, exp.Boolean)) and not j.args.get("using")  # bare JOIN parses as ON TRUE
            said_cross = (j.kind or "").upper() == "CROSS" and re.search(r"\bcross\s+join\b", sql, re.I)  # a comma join parses as CROSS too
            if no_condition and isinstance(j.this, exp.Table) and not said_cross and where is None:
                return (f"it joins {j.this.name} without a join condition, which pairs every row with every row. "
                        "Add the ON condition (find_join_path), or write CROSS JOIN if that is really intended.")
        if where is not None:
            conjuncts = list(where.this.flatten()) if isinstance(where.this, exp.And) else [where.this]
            for j in joins:
                if j.side.upper() != "LEFT" or not isinstance(j.this, exp.Table):
                    continue
                alias = j.this.alias_or_name.lower()
                for c in conjuncts:
                    if isinstance(c, (exp.Is, exp.Or)) or c.find(exp.Coalesce, exp.Is):
                        continue
                    if any(col.table.lower() == alias for col in c.find_all(exp.Column)):
                        return (f"it LEFT JOINs {j.this.name} but then filters on it in WHERE, which drops the rows "
                                "without a match, as an inner join would. Move the condition into the ON clause, or use "
                                "an inner join if that is intended.")
        if not joins or not sel.args.get("from_") or not isinstance(sel.args["from_"].this, exp.Table):
            continue
        tables = {t.alias_or_name.lower(): t.name.lower() for t in [sel.args["from_"].this, *(j.this for j in joins)]
                  if isinstance(t, exp.Table)}
        pk = {t.lower(): cols[0].lower() for t, cols in pks.items() if len(cols) == 1}
        repeated = set()  # aliases whose rows a join repeats: the "one" side of a one-to-many join
        for j in joins:
            on = j.args.get("on")
            for eq in (on.find_all(exp.EQ) if on is not None else []):
                a, b = eq.left, eq.right
                if not (isinstance(a, exp.Column) and isinstance(b, exp.Column)):
                    continue
                for one, many in ((a, b), (b, a)):
                    ot, mt = tables.get(one.table.lower()), tables.get(many.table.lower())
                    if ot and mt and pk.get(ot) == one.name.lower() and pk.get(mt) != many.name.lower():
                        repeated.add(one.table.lower())
        for agg in sel.find_all(exp.Sum, exp.Avg):
            if agg.find(exp.Distinct):
                continue
            cols = list(agg.find_all(exp.Column))
            if cols and all(c.table.lower() in repeated for c in cols):
                t = tables[cols[0].table.lower()]
                return (f"it sums or averages a column of {t} after joining a table with several rows per {t}, so each "
                        f"value is counted once per joined row. Aggregate the joined table in a subquery first, or "
                        "sum before joining. If the repetition is intended, present it again and say so.")
    return None


def build_agent(model: Model, output: Literal["tool", "prompted"] = "tool", retries: int = 2) -> Agent[Deps, Outcome]:
    """`model` comes from llm.build_model (any provider; settings such as caching travel with it).
    `output="prompted"` asks for the outcome as JSON in text, for models whose tool calls fail."""
    outputs: Any = ([ToolOutput(Report, name="present_report"), ToolOutput(Clarify, name="ask_clarifying_question"),
                     ToolOutput(Reply, name="reply")] if output == "tool" else PromptedOutput([Report, Clarify, Reply]))
    agent: Agent[Deps, Outcome] = Agent(
        model,
        deps_type=Deps,
        output_type=outputs,
        instructions=INSTRUCTIONS,
        retries=retries,
        name="rebo",
    )

    @agent.instructions
    def database_context(ctx: RunContext[Deps]) -> str:
        # Byte-identical across turns and users (changes only on bootstrap), so the instructions and
        # tool definitions form a cacheable prefix. Date and user go in the per-turn context block.
        app = ctx.deps.app
        tables = app.store.all("SELECT name, rows FROM cat_table ORDER BY name")
        listing = ", ".join(f"{t['name']}({t['rows'] if t['rows'] is not None else '?'})" for t in tables)
        return f"SQL dialect: {app.target.dialect}.\nTables (row counts): {listing}"

    @agent.tool
    def search_schema(ctx: RunContext[Deps], query: str) -> list[dict[str, Any]]:
        """Find tables and columns related to some business words. Returns best matches first."""
        app = ctx.deps.app
        hits = app.index.search_schema(query)
        out = []
        for h in hits:
            t = app.catalog.table_summary(h["table"]) or {}
            entry = {"table": h["table"], "rows": t.get("rows"), "about": t.get("description") or t.get("comment")}
            if h["column"]:
                c = app.store.one("SELECT type, description, comment, sensitive, top_values FROM cat_column "
                                  "WHERE table_name=? AND name=?", (h["table"], h["column"])) or {}
                entry.update(column=h["column"], type=c.get("type"),
                             column_about=c.get("description") or c.get("comment"))
                if c.get("sensitive"):
                    entry["protected"] = True
            out.append(entry)
        ctx.deps.trace.append({"tool": "search_schema", "query": query, "hits": len(out)})
        return out

    @agent.tool
    def describe_table(ctx: RunContext[Deps], table: str) -> dict[str, Any]:
        """Columns (type, null rate, distinct count, common values, meaning), keys and joins of one table."""
        app = ctx.deps.app
        d = app.catalog.describe_compact(table, app.knowledge.learned_joins(ctx.deps.user))
        ctx.deps.trace.append({"tool": "describe_table", "table": table, "found": bool(d)})
        if not d:
            raise ModelRetry(f"No table named '{table}'. Use search_schema.")
        return d

    @agent.tool
    def search_values(ctx: RunContext[Deps], text: str) -> list[dict[str, Any]]:
        """Find where a literal value (a status, stage, type, name, place) is stored. Returns
        table, column, the exact stored value and how many rows have it."""
        hits = ctx.deps.app.index.search_values(text)
        ctx.deps.trace.append({"tool": "search_values", "text": text, "hits": len(hits)})
        return [{k: h[k] for k in ("value", "table", "column", "freq")} for h in hits]

    @agent.tool
    def find_join_path(ctx: RunContext[Deps], from_table: str, to_table: str) -> list[str]:
        """Join conditions that connect two tables, shortest trusted path first."""
        app = ctx.deps.app
        path = app.catalog.join_path(from_table, to_table, app.knowledge.learned_joins(ctx.deps.user))
        ctx.deps.trace.append({"tool": "find_join_path", "from": from_table, "to": to_table, "found": path is not None})
        if path is None:
            return [f"No known path between {from_table} and {to_table}. Inspect both tables' columns for a "
                    "shared key, and ask the user if it is unclear."]
        return [f"{j['from_table']}.{j['from_cols']} = {j['to_table']}.{j['to_cols']} ({j['source']})" for j in path]

    @agent.tool
    def search_knowledge(ctx: RunContext[Deps], query: str) -> list[dict[str, Any]]:
        """Search what people taught: confirmed example reports, business terms, rules, joins."""
        items = ctx.deps.app.knowledge.search(ctx.deps.user, query)
        ctx.deps.trace.append({"tool": "search_knowledge", "query": query, "hits": len(items)})
        return [ctx.deps.app.knowledge_for_prompt(i, ctx.deps.user) for i in items]

    @agent.tool
    def run_sql(ctx: RunContext[Deps], sql: str) -> dict[str, Any]:
        """Run a small read-only SELECT to check an assumption. Returns at most 20 rows."""
        deps = ctx.deps
        deps.probes += 1
        if deps.probes > 12:
            return {"error": "Probe budget used up. Present the report now or ask the user."}
        app = deps.app
        try:
            g = guard(sql, dialect=app.target.dialect, schema=app.catalog.schema, sensitive=app.catalog.sensitive,
                      allowed_tables=app.allowed_tables, row_cap=app.settings.probe_row_limit + 1)
            res = app.target.run(g.sql, max_rows=app.settings.probe_row_limit)
        except GuardError as e:
            deps.trace.append({"tool": "run_sql", "error": str(e)})
            return {"error": str(e)}
        except Exception as e:
            msg = str(getattr(e, "orig", e))[:400]
            deps.trace.append({"tool": "run_sql", "error": msg})
            return {"error": f"Database error: {msg}"}
        deps.trace.append({"tool": "run_sql", "rows": len(res.rows), "ms": res.elapsed_ms})
        return {"columns": res.columns, "rows": res.rows, "more_rows": res.truncated, "ms": res.elapsed_ms}

    @agent.output_validator
    def validate(ctx: RunContext[Deps], output: Outcome) -> Outcome:
        if not isinstance(output, Report):
            return output
        app, deps = ctx.deps.app, ctx.deps
        try:
            g = guard(output.sql, dialect=app.target.dialect, schema=app.catalog.schema,
                      sensitive=app.catalog.sensitive, allowed_tables=app.allowed_tables,
                      row_cap=app.settings.row_limit + 1)
            res = app.target.run(g.sql, max_rows=app.settings.row_limit)
        except GuardError as e:
            raise ModelRetry(f"The report SQL was rejected: {e}") from e
        except Exception as e:
            raise ModelRetry(f"The report SQL failed in the database: {str(getattr(e, 'orig', e))[:400]}") from e
        for check in app.sql_checks:  # host adapter rules, e.g. JMS Report Builder compatibility
            if problem := check(g.sql):
                raise ModelRetry(f"The report SQL is valid but {problem}")
        trap = None if deps.trap_retry else sql_trap(g.sql, app.target.dialect, app.catalog.primary_keys)
        if trap:
            deps.trap_retry = True
            raise ModelRetry(f"The report SQL runs, but {trap}")
        if not res.rows and not deps.zero_row_retry:
            deps.zero_row_retry = True
            raise ModelRetry("The report returned 0 rows. Check each literal filter with search_values and each "
                             "join with a count. If 0 rows is genuinely right, present it again and say why in "
                             "the assumptions.")
        key = None if deps.grain_retry else entity_key(g.sql, app.target.dialect, app.catalog.primary_keys)
        if key and len(res.rows) > len({r[key[0]] for r in res.rows}):
            deps.grain_retry = True
            raise ModelRetry(f"The rows repeat per {key[1]}: {len(res.rows)} rows but only "
                             f"{len({r[key[0]] for r in res.rows})} distinct {key[1]} values, because a joined table "
                             f"has several rows for each. One row per {key[1]} was probably intended: aggregate or "
                             f"pick one row. If one row per joined record is intended, present it again and say so "
                             "in the assumptions.")
        near = [] if deps.shape_retry or output.used_knowledge or not app.settings.shape_check \
            else app.shape_matches(deps.user, g.sql, exclude=deps.shown)
        if near:
            deps.shape_retry = True
            listed = "\n".join(f"- id {i['id']}: \"{i['title']}\" (asked as \"{i.get('question') or i['title']}\"), "
                               f"{round(sim * 100)}% the same shape: {i['sql']}" for i, sim in near)
            raise ModelRetry("Saved reports with nearly the same query shape exist, but you did not see them:\n"
                             f"{listed}\nIf one of them answers this question, adapt it (change only values, dates, "
                             "grouping) and list its id in used_knowledge. If none does, present your report again "
                             "unchanged.")
        deps.final, deps.final_sql = res, g.sql
        return output

    return agent
