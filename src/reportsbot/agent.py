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

import datetime as dt
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

import sqlglot
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput
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


class Clarify(BaseModel):
    """Ask before running, because reasonable readings give materially different answers.
    All open questions go into ONE clarify turn, so the user answers once."""
    questions: list[Question] = Field(min_length=1, max_length=3)
    why: str = Field(description="One sentence: what differs between the readings")


class Reply(BaseModel):
    """A plain answer when the message is not a report request."""
    text: str
    learnable: list[Learnable] = Field(default_factory=list)


Outcome = Report | Clarify | Reply


@dataclass
class Deps:
    app: "App"
    user: "User"
    trace: list[dict[str, Any]] = field(default_factory=list)
    final: QueryResult | None = None
    final_sql: str | None = None
    zero_row_retry: bool = False
    grain_retry: bool = False
    probes: int = 0


INSTRUCTIONS = """\
You build database reports for business users who do not know SQL or the schema.

How to work
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


def build_agent(model: Model) -> Agent[Deps, Outcome]:
    """`model` comes from llm.build_model (any provider; settings such as caching travel with it)."""
    agent: Agent[Deps, Outcome] = Agent(
        model,
        deps_type=Deps,
        output_type=[ToolOutput(Report, name="present_report"), ToolOutput(Clarify, name="ask_clarifying_question"),
                     ToolOutput(Reply, name="reply")],
        instructions=INSTRUCTIONS,
        retries=2,
        name="reportsbot",
    )

    @agent.instructions
    def database_context(ctx: RunContext[Deps]) -> str:
        app = ctx.deps.app
        tables = app.store.all("SELECT name, rows FROM cat_table ORDER BY name")
        listing = ", ".join(f"{t['name']}({t['rows'] if t['rows'] is not None else '?'})" for t in tables)
        return (f"Today is {dt.date.today().isoformat()}. SQL dialect: {app.target.dialect}. "
                f"The user is a {ctx.deps.user.role} whose id in the host application is "
                f"'{ctx.deps.user.id}' (use it for 'my' / 'me' when a table stores that id).\n"
                f"Tables (row counts): {listing}")

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
        d = app.catalog.describe(table, app.knowledge.learned_joins(ctx.deps.user))
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
        deps.final, deps.final_sql = res, g.sql
        return output

    return agent
