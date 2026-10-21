"""Application service: the one object the API, UI, CLI and MCP adapter talk to.

Every public method returns plain JSON-able dicts so any front end can render them.
Flow per user message: retrieve context -> agent loop -> validated outcome -> turn record.
Flow per feedback: lifecycle transition in Knowledge -> message from messages.py.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from collections import Counter
from functools import cached_property
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import (Agent, ModelMessage, ModelMessagesTypeAdapter, ModelRetry, ToolOutput, UsageLimitExceeded,
                         UsageLimits)
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

from . import messages as msg
from .agent import Clarify, Deps, Report, Reply, build_agent
from .catalog import Catalog, bootstrap
from .knowledge import Knowledge, User
from .llm import build_model, credentials_present, profile
from .observability import setup_tracing
from .retrieval import Index, fts_query, get_embedder
from .safety import canonical_hash, drill_sql, fill_params, guard
from .settings import Settings, get_settings, load_env_file
from .store import Store, new_id, now
from .target import QueryResult, TargetDB

log = logging.getLogger(__name__)
_KEEP_RUNS = 4  # earlier user turns kept in the model's message history


def _norm_question(text: str) -> str:
    return " ".join(text.lower().split()).rstrip(" ?.!")


class ColumnDoc(BaseModel):
    name: str
    meaning: str = Field(description="Short meaning, grounded in the name, type, statistics and sample values")


class TableDoc(BaseModel):
    table: str = Field(description="One or two sentences: what one row of this table represents and what it is used for")
    columns: list[ColumnDoc] = Field(default_factory=list, description=(
        "Every column whose name is not self-explanatory: abbreviations, codes, flags, statuses, "
        "ids pointing to other tables, dates with a specific business meaning. Skip only obvious ones "
        "like created, updated, first_name."))


class ParamFill(BaseModel):
    """Whether a new request is a saved report with only its values changed, and the new values."""
    same_report: bool = Field(description=(
        "true only if the new request asks for the same report and differs only in values (names, statuses, "
        "dates, numbers); false if it changes what is selected, grouped, joined or filtered on"))
    values: list[str | int | float] = Field(default_factory=list, description=(
        "When same_report: one value per placeholder :p1, :p2, ... in order, spelled as in saved_values; "
        "unchanged ones copied as they are"))


class Review(BaseModel):
    ok: bool = Field(description="true when the report answers the question as asked")
    concern: str = Field("", description="When not ok: the one thing a person should check, in plain words")


class App:
    def __init__(self, settings: Settings | None = None):
        load_env_file()  # API keys from .env into the environment (explicit settings objects too)
        self.settings = s = settings or get_settings()
        self.store = Store(s.state_db)
        self.target = TargetDB(s.database_url, timeout_s=s.query_timeout_s)
        self.index = Index(self.store, get_embedder(s.embeddings))
        self.catalog = Catalog(self.store)
        self.knowledge = Knowledge(self.store, self.index, self.catalog, self.target.dialect, s.share_threshold)
        self.allowed_tables = {t.strip() for t in s.allow_tables.split(",") if t.strip()} or None
        setup_tracing()

    @cached_property
    def agent(self) -> Agent:
        s = self.settings
        if not credentials_present(s.model, s):
            raise RuntimeError(f"No API key in the environment for model '{s.model}' (see .env.example)")
        return build_agent(build_model(s.model, s, s.fallback_models), output=profile(s.model).output)

    @cached_property
    def fast_agent_model(self):
        s = self.settings
        return build_model(s.fast_model, s)

    @cached_property
    def param_agent(self) -> Agent:
        return Agent(output_type=ToolOutput(ParamFill, name="fill_parameters"), retries=1, instructions=(
            "A user's new request is compared with a saved report. Decide whether it asks for the same report "
            "with only different values, and if so give the new value for every placeholder."))

    @cached_property
    def review_agent(self) -> Agent:
        return Agent(output_type=ToolOutput(Review, name="review"), retries=1, instructions=(
            "You check a database report before a business user sees it. Given the question, the SQL, the "
            "assumptions made and the first rows, decide whether the report answers the question. Flag only a "
            "concrete problem a person should check (wrong filter, wrong grain, missing condition, a reading "
            "that contradicts the question), in one plain sentence without table or column names. "
            "Otherwise ok."))

    @cached_property
    def escalation_model(self):
        s = self.settings
        return build_model(s.escalate_model, s) if s.escalate_model else None

    # ---- bootstrap / maintenance ----------------------------------------------------------
    def bootstrap(self, *, describe: bool = False, progress=print) -> dict[str, int]:
        describer = self._describe_table if describe else None
        counts = bootstrap(self.target, self.store, self.index, allow=self.allowed_tables,
                           deny_columns=self.settings.deny_columns, describe=describer, progress=progress)
        self.catalog.refresh()
        counts.update({f"knowledge_{k}": v for k, v in self.revalidate().items()})
        return counts

    def _describe_table(self, payload: dict[str, Any]) -> dict[str, Any]:
        async def go() -> TableDoc:
            model = build_model(self.settings.fast_model, self.settings)  # per call: one event loop per thread
            agent = Agent(model, output_type=TableDoc, retries=2, instructions=(
                "You document a database table for analysts from its structure and statistics. Be factual: "
                "describe only what the column names, types, foreign keys and sample values support. If unsure, "
                "say what it appears to be. Never invent business rules."))

            @agent.output_validator
            def substantive(doc: TableDoc) -> TableDoc:
                if len(doc.table.split()) < 6:
                    raise ModelRetry("The table description must be a full sentence about what a row represents.")
                return doc

            return (await agent.run(json.dumps(payload, default=str)[:24000])).output

        doc = asyncio.run(go())
        known = {c["name"] for c in payload["columns"]}
        return {"table": doc.table, "columns": {c.name: c.meaning for c in doc.columns if c.name in known}}

    def same_result(self, sql_a: str, sql_b: str) -> bool:
        """True when two queries return the same non-empty multiset of rows (column order and
        names ignored). How independent confirmations of differently written SQL are recognised."""
        def rows(sql: str):
            g = guard(sql, dialect=self.target.dialect, schema=self.catalog.schema, sensitive=self.catalog.sensitive,
                      allowed_tables=self.allowed_tables, row_cap=self.settings.row_limit + 1)
            r = self.target.run(g.sql, max_rows=self.settings.row_limit)
            return None if r.truncated else Counter(tuple(sorted(map(str, row))) for row in r.rows)
        a = rows(sql_a)
        return bool(a) and a == rows(sql_b)

    def revalidate(self) -> dict[str, int]:
        def check(sql: str) -> None:
            g = guard(sql, dialect=self.target.dialect, schema=self.catalog.schema, sensitive=self.catalog.sensitive,
                      allowed_tables=self.allowed_tables, row_cap=1)
            self.target.run(g.sql, max_rows=1)
        return self.knowledge.revalidate(check)

    # ---- context for the model --------------------------------------------------------------
    def knowledge_for_prompt(self, item: dict[str, Any], user: User) -> dict[str, Any]:
        trust = ("verified" if item["status"] == "verified" else
                 "yours" if item["owner"] == user.id else item["status"])
        out = {"id": item["id"], "kind": item["kind"], "trust": trust, "title": item["title"]}
        for k in ("question", "body", "sql"):
            if item.get(k):
                out[k] = item[k]
        if item["kind"] == "example":
            out["confirmed_by"] = len(item.get("confirmers") or [])
        return out

    def _reuse_match(self, user: User, text: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
        """A trusted saved example (verified, or the user's own) whose question shares >= 60% of its
        content words with this one. Such turns only adapt saved SQL, so the fast model handles them."""
        words = set(fts_query(text).replace('"', "").replace("*", "").split(" OR "))
        for i in items:
            if i["kind"] != "example" or not (i["status"] == "verified" or i["owner"] == user.id):
                continue
            theirs = set(fts_query(i.get("question") or "").replace('"', "").replace("*", "").split(" OR "))
            if words and theirs and len(words & theirs) / len(words | theirs) >= 0.6:
                return i
        return None

    def _context_block(self, user: User, text: str, items: list[dict[str, Any]] | None = None) -> str:
        items = self.knowledge.search(user, text, top=6) if items is None else items
        hits = self.index.search_schema(text, top=20)
        tables = list(dict.fromkeys(h["table"] for h in hits))[:8]
        values = self.index.search_values(text, top=8)
        parts = [f"<turn>Today is {dt.date.today().isoformat()}. The user is a {user.role} whose id in the host "
                 f"application is '{user.id}' (use it for 'my' / 'me' when a table stores that id).</turn>",
                 "<learned_knowledge>"]
        parts += [json.dumps(self.knowledge_for_prompt(i, user), default=str) for i in items] or ["(none yet)"]
        parts += ["</learned_knowledge>", "<likely_tables>"]
        for t in tables:
            s = self.catalog.table_summary(t) or {}
            parts.append(f"{t} ({s.get('rows')} rows){': ' + s['description'] if s.get('description') else ''}")
        parts += ["</likely_tables>", "<value_matches>"]
        parts += [f"'{v['value']}' is stored in {v['table']}.{v['column']} ({v['freq']} rows)" for v in values]
        parts += ["</value_matches>", f"<request>{text}</request>"]
        return "\n".join(parts)

    # ---- conversations --------------------------------------------------------------------
    def _load_history(self, conversation_id: str) -> list[ModelMessage]:
        row = self.store.one("SELECT messages FROM conversation WHERE id=?", (conversation_id,))
        if not row:
            return []
        history = ModelMessagesTypeAdapter.validate_json(row["messages"])
        starts = [i for i, m in enumerate(history)
                  if isinstance(m, ModelRequest) and any(isinstance(p, UserPromptPart) for p in m.parts)]
        return history[starts[-_KEEP_RUNS]:] if len(starts) > _KEEP_RUNS else history

    def _provenance(self, user: User, sql: str, used: list[str]) -> dict[str, Any]:
        canon = canonical_hash(sql, self.target.dialect)
        visible = self.knowledge.visible_ids(user)
        same = [i for i in self.store.all("SELECT * FROM knowledge WHERE kind='example' AND sql_canonical=?", (canon,))
                if i["id"] in visible]
        verified = next((i for i in same if i["status"] == "verified"), None)
        if verified:
            when = dt.datetime.fromtimestamp(verified["verified_at"] or verified["updated_at"]).date().isoformat()
            return {"label": "verified", "item_ids": [verified["id"]],
                    "text": msg.say("prov_verified", who=verified["verified_by"] or "an admin", when=when)}
        if same:
            return {"label": "yours", "item_ids": [same[0]["id"]], "text": msg.say("prov_yours")}
        used_items = [self.knowledge.get(i) for i in used if i in visible]
        used_items = [i for i in used_items if i]
        if used_items:
            return {"label": "adapted", "item_ids": [i["id"] for i in used_items],
                    "text": msg.say("prov_adapted", titles=", ".join(f"“{i['title']}”" for i in used_items))}
        return {"label": "new", "item_ids": [], "text": msg.say("prov_new")}

    def _suggestions(self, user: User, turn_id: str, learnable) -> list[dict[str, Any]]:
        out = []
        with self.store.tx() as db:
            for item in learnable or []:
                sid = new_id("sg")
                payload = item.model_dump()
                db.execute("INSERT INTO suggestion(id, turn_id, owner, payload, created_at) VALUES(?,?,?,?,?)",
                           (sid, turn_id, user.id, json.dumps(payload), now()))
                out.append({"id": sid, **payload})
        return out

    async def ask(self, user: User, text: str, conversation_id: str | None = None) -> dict[str, Any]:
        conv_id = conversation_id or new_id("conv")
        if not self.store.one("SELECT id FROM conversation WHERE id=?", (conv_id,)):
            with self.store.tx() as db:
                db.execute("INSERT INTO conversation(id, owner, created_at, updated_at) VALUES(?,?,?,?)",
                           (conv_id, user.id, now(), now()))
        history = self._load_history(conv_id)
        self._remember_clarification(user, conv_id, text)
        if direct := self._direct_answer(user, conv_id, text, history):
            return direct
        deps = Deps(app=self, user=user)
        turn_id = new_id("turn")
        items = self.knowledge.search(user, text, top=6)
        prompt = self._context_block(user, text, items)
        # Routing: a trusted saved report with new values -> filled in by the fast model, no agent;
        # adapting one otherwise -> agent on the fast model; anything new -> agent model.
        reuse = self._reuse_match(user, text, items)
        if reuse and (filled := await self._param_answer(user, conv_id, text, history, reuse)):
            return filled
        reuse = reuse if self.settings.fast_model != self.settings.model else None
        first_model, first_name = (self.fast_agent_model, self.settings.fast_model) if reuse else (None, self.settings.model)
        limits = self._limits(first_name)
        escalated = False
        try:
            try:
                result = await self.agent.run(prompt, deps=deps, message_history=history, usage_limits=limits,
                                              model=first_model)
            except Exception as first:
                # Cost cascade: the cheap model failed (SQL never validated, budget, API error) ->
                # one retry on the stronger escalation model, from a clean slate.
                if not self.escalation_model:
                    raise
                log.info("escalating after %s: %s", type(first).__name__, str(first)[:200])
                deps = Deps(app=self, user=user, trace=[*deps.trace, {"tool": "escalate", "after": type(first).__name__}])
                escalated = True
                result = await self.agent.run(prompt, deps=deps, message_history=history,
                                              usage_limits=self._limits(self.settings.escalate_model),
                                              model=self.escalation_model)
        except UsageLimitExceeded:
            return self._record(turn_id, conv_id, user, text, "error", {"message": msg.say("error_budget")}, deps)
        except Exception:
            log.exception("agent run failed")
            return self._record(turn_id, conv_id, user, text, "error", {"message": msg.say("error_generic")}, deps)

        all_msgs = [*history, *result.new_messages()]
        with self.store.tx() as db:
            db.execute("UPDATE conversation SET messages=?, updated_at=? WHERE id=?",
                       (ModelMessagesTypeAdapter.dump_json(all_msgs).decode(), now(), conv_id))
        out = result.output
        usage = result.usage
        usage_d = {"requests": usage.requests, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                   "cache_read_tokens": getattr(usage, "cache_read_tokens", None), "tool_calls": usage.tool_calls,
                   "model": self.settings.escalate_model if escalated else first_name, "escalated": escalated,
                   "route": "reuse" if reuse and not escalated else "new"}
        if isinstance(out, Report) and deps.final is not None:
            await self._second_opinion(user, text, out, deps.final, usage_d)
            return self._report_turn(turn_id, conv_id, user, text, out, deps.final, deps, usage_d)
        if isinstance(out, Clarify):
            gated = self._ask_gate(out, text)
            usage_d["gate"] = "answered" if gated else "asked"
            if gated:
                return self._report_turn(turn_id, conv_id, user, text, *gated, deps, usage_d)
            payload = {"intro": msg.say("clarify_intro"), "why": out.why,
                       "questions": [q.model_dump(exclude={"option_sql"}) for q in out.questions]}
            return self._record(turn_id, conv_id, user, text, "clarify", payload, deps, usage=usage_d)
        reply = out if isinstance(out, Reply) else Reply(text=str(out))
        visible = self.knowledge.visible_ids(user)
        cites = [self.knowledge_for_prompt(i, user) for i in map(self.knowledge.get, reply.used_knowledge)
                 if i and i["id"] in visible]
        payload = {"text": reply.text, "cites": [{k: c[k] for k in ("id", "title", "trust")} for c in cites],
                   "suggestions": self._suggestions(user, turn_id, reply.learnable)}
        return self._record(turn_id, conv_id, user, text, "answer", payload, deps, usage=usage_d)

    def _remember_clarification(self, user: User, conv_id: str, text: str) -> None:
        """An answer to the previous turn's clarifying question(s) becomes a personal note titled with
        the question, so this user is not asked the same thing again (docs/22 §2). Answers arrive as
        "Q → A" pairs joined by "; ", or as a bare option when there was one question. Only answers
        that are one of the offered options are kept; other text is a new request, not an answer."""
        prev = self.store.one("SELECT id, kind, question, payload FROM turn WHERE conversation_id=? AND owner=? "
                              "ORDER BY created_at DESC LIMIT 1", (conv_id, user.id))
        if not prev or prev["kind"] != "clarify":
            return
        questions = {q["question"].strip(): q["options"] for q in json.loads(prev["payload"])["questions"]}
        for part in text.split(";"):
            q, sep, a = part.partition("→")
            q, a = (q.strip(), a.strip()) if sep else (next(iter(questions)) if len(questions) == 1 else "", q.strip())
            option = next((o for o in questions.get(q, []) if o.strip().lower() == a.lower()), None)
            if option:
                self.knowledge.teach(user, kind="note", title=q, body=option, sql=None, source_turn=prev["id"],
                                     question=prev["question"])

    def _report_turn(self, turn_id, conv_id, user, text, out: Report, res: QueryResult, deps, usage_d):
        prov = self._provenance(user, out.sql, out.used_knowledge)
        self.knowledge.mark_used(prov["item_ids"])
        payload = {"title": out.title, "sql": out.sql, "columns": res.columns, "rows": res.rows,
                   "truncated": res.truncated, "elapsed_ms": res.elapsed_ms, "assumptions": out.assumptions,
                   "provenance": prov, "follow_ups": out.follow_ups,
                   "message": msg.say("report_ready", title=out.title,
                                      row_phrase=msg.rows_phrase(len(res.rows), res.truncated)),
                   "suggestions": self._suggestions(user, turn_id, out.learnable)}
        return self._record(turn_id, conv_id, user, text, "report", payload, deps, sql=out.sql, prov=prov,
                            usage=usage_d)

    async def _second_opinion(self, user: User, text: str, out: Report, res: QueryResult, usage_d: dict) -> None:
        """A new report resting on more than 2 assumptions gets one review by the fast model; a concern
        is added as a "Check: ..." assumption. usage.review = ok | concern (absent when not reviewed)."""
        if len(out.assumptions) <= 2 or self._provenance(user, out.sql, out.used_knowledge)["label"] != "new":
            return
        prompt = json.dumps({"question": text, "sql": out.sql, "assumptions": out.assumptions,
                             "columns": res.columns, "first_rows": res.rows[:10], "row_count": len(res.rows)},
                            default=str)
        try:
            review = (await self.review_agent.run(prompt, model=self.fast_agent_model)).output
        except Exception:
            log.info("second opinion failed; report shown without it", exc_info=True)
            return
        usage_d["review"] = "ok" if review.ok or not review.concern.strip() else "concern"
        if usage_d["review"] == "concern":
            out.assumptions.append(msg.say("review_concern", concern=review.concern.strip()))

    def _limits(self, model_spec: str) -> UsageLimits:
        tool_calls = round(self.settings.max_tool_calls * profile(model_spec).tool_call_factor)
        return UsageLimits(request_limit=40, tool_calls_limit=tool_calls)

    def _run_report_sql(self, sql: str) -> QueryResult:
        g = guard(sql, dialect=self.target.dialect, schema=self.catalog.schema, sensitive=self.catalog.sensitive,
                  allowed_tables=self.allowed_tables, row_cap=self.settings.row_limit + 1)
        return self.target.run(g.sql, max_rows=self.settings.row_limit)

    def _direct_answer(self, user: User, conv_id: str, text: str, history: list[ModelMessage]) -> dict | None:
        """The user's own confirmed example asked with exactly the same words (case, spacing and end
        punctuation ignored) is answered by re-running its SQL: no model call, route "direct"."""
        key = _norm_question(text)
        item = next((i for i in self.knowledge.visible(user, "example")
                     if i["owner"] == user.id and i.get("question") and _norm_question(i["question"]) == key), None)
        if not item:
            return None
        usage_d = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "tool_calls": 0,
                   "model": None, "escalated": False, "route": "direct"}
        return self._answer_from_saved(user, conv_id, text, history, item, item["sql"], usage_d)

    async def _param_answer(self, user: User, conv_id: str, text: str, history: list[ModelMessage],
                            item: dict[str, Any]) -> dict | None:
        """A trusted example matched and has a template: if the fast model says the request only changes
        its values, fill them in (as syntax-tree literals) and run, route "params". Anything else: None."""
        if not item.get("sql_template") or not item.get("params"):
            return None
        prompt = json.dumps({"saved_question": item.get("question"), "sql_template": item["sql_template"],
                             "saved_values": item["params"], "new_request": text})
        try:
            result = await self.param_agent.run(prompt, model=self.fast_agent_model)
            fill = result.output
            if not fill.same_report or len(fill.values) != len(item["params"]):
                return None
            sql = fill_params(item["sql_template"], self.target.dialect, fill.values)
        except Exception:
            log.info("parameter fill failed for %s; using the agent", item["id"], exc_info=True)
            return None
        u = result.usage
        usage_d = {"requests": u.requests, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                   "cache_read_tokens": getattr(u, "cache_read_tokens", None), "tool_calls": u.tool_calls,
                   "model": self.settings.fast_model, "escalated": False, "route": "params"}
        return self._answer_from_saved(user, conv_id, text, history, item, sql, usage_d, empty_ok=False)

    def _answer_from_saved(self, user, conv_id, text, history, item, sql, usage_d, *, empty_ok=True) -> dict | None:
        try:
            res = self._run_report_sql(sql)
        except Exception:
            log.info("saved report %s failed; using the agent", item["id"], exc_info=True)
            return None
        if not res.rows and not empty_ok:
            return None  # new values matched nothing: let the agent check the spelling
        src = self.store.one("SELECT payload FROM turn WHERE id=?", (item["source_turn"],)) if item["source_turn"] else None
        out = Report(title=item["title"], sql=sql, used_knowledge=[item["id"]],
                     assumptions=json.loads(src["payload"]).get("assumptions") or [] if src else [])
        note = f"(Answered from saved report {item['id']}, route {usage_d['route']}.) {out.title}: {sql}"
        msgs = [*history, ModelRequest(parts=[UserPromptPart(text)]), ModelResponse(parts=[TextPart(note)])]
        with self.store.tx() as db:
            db.execute("UPDATE conversation SET messages=?, updated_at=? WHERE id=?",
                       (ModelMessagesTypeAdapter.dump_json(msgs).decode(), now(), conv_id))
        deps = Deps(app=self, user=user, trace=[{"tool": usage_d["route"], "item": item["id"]}])
        return self._report_turn(new_id("turn"), conv_id, user, text, out, res, deps, usage_d)

    def _ask_gate(self, out: Clarify, text: str) -> tuple[Report, QueryResult] | None:
        """Deterministic ask-gate: when every question's first two readings return the same rows,
        asking is pointless; answer with question 1's first reading and say so (docs/04 §5)."""
        for q in out.questions:
            if len(q.option_sql) < 2:
                return None
            try:
                if not self.same_result(q.option_sql[0], q.option_sql[1]):
                    return None
            except Exception:  # unrunnable or rejected SQL: cannot prove the readings agree
                return None
        sql = out.questions[0].option_sql[0]
        res = self._run_report_sql(sql)
        notes = [msg.say("gate_same", q=q.question, options=" / ".join(f"“{o}”" for o in q.options[:2]))
                 for q in out.questions]
        return Report(title=text.strip()[:80], sql=sql, assumptions=notes), res

    def _record(self, turn_id, conv_id, user, question, kind, payload, deps, *, sql=None, prov=None, usage=None):
        with self.store.tx() as db:
            db.execute("INSERT INTO turn(id, conversation_id, owner, question, kind, payload, sql, provenance, usage,"
                       " created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (turn_id, conv_id, user.id, question, kind, json.dumps(payload, default=str), sql,
                        json.dumps(prov) if prov else None, json.dumps(usage) if usage else None, now()))
        return {"turn_id": turn_id, "conversation_id": conv_id, "kind": kind, **payload, "trace": deps.trace}

    # ---- feedback & teaching ------------------------------------------------------------------
    def _turn(self, user: User, turn_id: str) -> dict[str, Any]:
        t = self.store.one("SELECT * FROM turn WHERE id=?", (turn_id,))
        if not t or t["owner"] != user.id:
            raise PermissionError("Feedback can only be given on your own answers.")
        return t

    def feedback(self, user: User, turn_id: str, verdict: str, note: str = "") -> dict[str, Any]:
        t = self._turn(user, turn_id)
        if t["kind"] != "report":
            raise ValueError("Only reports can be confirmed or rejected.")
        payload = json.loads(t["payload"])
        if t["feedback"]:
            self.undo_feedback(user, turn_id)  # changing your mind replaces the earlier feedback
        with self.store.tx() as db:
            db.execute("UPDATE turn SET feedback=?, feedback_note=? WHERE id=?", (verdict, note.strip() or None, turn_id))
        if verdict == "correct":
            o = self.knowledge.confirm_report(
                user, question=t["question"], title=payload["title"], sql=t["sql"], turn_id=turn_id,
                result_signature={"columns": payload["columns"], "rows": len(payload["rows"]),
                                  "truncated": payload["truncated"]},
                equivalent=self.same_result)
            text = msg.say(o.message)
            if o.extra.get("auto_proposed"):
                text += " " + msg.say("confirm_auto_proposed", n=o.extra["auto_proposed"])
            return {"message": text, "item": o.item}
        prov = json.loads(t["provenance"] or "{}")
        outcomes = self.knowledge.reject(user, prov.get("item_ids", []), note, turn_id=turn_id)
        texts = [msg.say(o.message) for o in outcomes]
        out = {"message": " ".join([*texts, msg.say("fix_prompt")]), "items": [o.item for o in outcomes],
               "next": "correction"}
        if note.strip():  # feedback given in full words doubles as the correction to run next
            out["correction"] = f"Correction to the previous report: {note.strip()}"
            out["message"] = " ".join([*texts, msg.say("fix_with_words")])
        return out

    def undo_feedback(self, user: User, turn_id: str) -> dict[str, Any]:
        t = self._turn(user, turn_id)
        if not t["feedback"]:
            raise ValueError("There is no feedback on this answer to undo.")
        touched = self.knowledge.undo_feedback(user, turn_id)
        with self.store.tx() as db:
            db.execute("UPDATE turn SET feedback=NULL, feedback_note=NULL WHERE id=?", (turn_id,))
        return {"message": msg.say("feedback_undone"), "items": touched}

    # ---- requests: asking someone else to change what you can't ------------------------------
    def create_request(self, user: User, *, kind: str, text: str, item_id: str | None = None,
                       turn_id: str | None = None) -> dict[str, Any]:
        if kind not in ("fix_knowledge", "fix_report", "access", "config", "other"):
            raise ValueError("kind must be fix_knowledge, fix_report, access, config or other")
        if not text.strip():
            raise ValueError("Describe what should change, in your own words.")
        target = "owner" if kind in ("access", "config") else "admin"
        rid = new_id("rq")
        with self.store.tx() as db:
            db.execute("INSERT INTO request(id, kind, target, requester, item_id, turn_id, text, created_at, updated_at) "
                       "VALUES(?,?,?,?,?,?,?,?,?)", (rid, kind, target, user.id, item_id, turn_id, text.strip(), now(), now()))
        return {"message": msg.say("request_sent", who="an owner" if target == "owner" else "an admin"),
                "request": self.store.one("SELECT * FROM request WHERE id=?", (rid,))}

    def list_requests(self, user: User, status: str | None = "open") -> list[dict[str, Any]]:
        if user.is_owner:
            where, args = "1=1", ()
        elif user.is_admin:
            where, args = "(target='admin' OR requester=?)", (user.id,)
        else:
            where, args = "requester=?", (user.id,)
        if status:
            where += " AND status=?"
            args = (*args, status)
        return self.store.all(f"SELECT * FROM request WHERE {where} ORDER BY created_at", args)

    def resolve_request(self, user: User, request_id: str, status: str, resolution: str = "") -> dict[str, Any]:
        r = self.store.one("SELECT * FROM request WHERE id=?", (request_id,))
        if not r:
            raise KeyError(request_id)
        if not (user.is_owner or (user.is_admin and r["target"] == "admin")):
            raise PermissionError("Only an admin (or an owner, for access and configuration) can resolve this.")
        if status not in ("done", "declined"):
            raise ValueError("status must be done or declined")
        with self.store.tx() as db:
            db.execute("UPDATE request SET status=?, resolver=?, resolution=?, updated_at=? WHERE id=?",
                       (status, user.id, resolution, now(), request_id))
        return {"message": msg.say(f"request_{status}"), "request": self.store.one("SELECT * FROM request WHERE id=?",
                                                                                  (request_id,))}

    def remember(self, user: User, suggestion_id: str, accept: bool) -> dict[str, Any]:
        s = self.store.one("SELECT * FROM suggestion WHERE id=? AND owner=?", (suggestion_id, user.id))
        if not s or s["state"] != "open":
            raise KeyError("No open suggestion with that id.")
        with self.store.tx() as db:
            db.execute("UPDATE suggestion SET state=? WHERE id=?", ("accepted" if accept else "dismissed", suggestion_id))
        if not accept:
            return {"message": msg.say("remember_dismissed")}
        p = json.loads(s["payload"])
        o = self.knowledge.teach(user, kind=p["kind"], title=p["title"], body=p["body"], sql=p.get("sql"),
                                 source_turn=s["turn_id"])
        extra = {"shared_body": o.extra["shared"]["body"]} if "shared" in o.extra else {}
        return {"message": msg.say(o.message, title=p["title"], **extra), "item": o.item}

    def share(self, user: User, item_id: str) -> dict[str, Any]:
        o = self.knowledge.share(user, item_id)
        return {"message": msg.say(o.message, scope="the whole organisation", title=o.item["title"]), "item": o.item}

    def promote(self, user: User, item_id: str, scope: str = "org") -> dict[str, Any]:
        o = self.knowledge.promote(user, item_id, scope)
        where = "your team" if o.item["scope"] == "team" else "the whole organisation"
        return {"message": msg.say("promoted", scope=where, title=o.item["title"]), "item": o.item}

    def retire(self, user: User, item_id: str, reason: str = "") -> dict[str, Any]:
        o = self.knowledge.retire(user, item_id, reason)
        return {"message": msg.say("retired"), "item": o.item}

    def restore(self, user: User, item_id: str) -> dict[str, Any]:
        o = self.knowledge.restore(user, item_id)
        if o.message == "edit_undone":
            return {"message": msg.say("edit_undone", title=o.item["title"]), "item": o.item}
        return {"message": msg.say("restored", title=o.item["title"],
                                   status=msg.status_label(o.item["status"], o.item["scope"]).lower()),
                "item": o.item}

    def starter_questions(self, user: User, top: int = 5) -> list[str]:
        """Questions behind the user's pinned reports, then the most-used reports this user can trust:
        shown as one-click starters (a pinned one re-runs with no model call, route "direct")."""
        rows = [i for i in self.knowledge.visible(user, "example") if i.get("question")]
        rows.sort(key=lambda i: (not (i["pinned"] and i["owner"] == user.id), i["status"] != "verified",
                                 -(i["uses"] or 0), -(i["confirmations"] or 0)))
        return list(dict.fromkeys(i["question"] for i in rows))[:top]

    def about(self, user: User, q: str) -> dict[str, Any]:
        """"What do you know about X?": the visible learned items grouped by trust, matching tables and
        columns with their descriptions, and stored values. No model call (docs/22 §2)."""
        groups: dict[str, list[dict[str, Any]]] = {"verified": [], "yours": [], "pending": []}
        for item in self.knowledge.search(user, q, top=10):
            p = self.knowledge_for_prompt(item, user)
            groups[p["trust"] if p["trust"] in ("verified", "yours") else "pending"].append(p)
        schema = []
        for h in self.index.search_schema(q, top=10):
            t = self.catalog.table_summary(h["table"]) or {}
            entry = {"table": h["table"], "about": t.get("description") or t.get("comment")}
            if h["column"]:
                c = self.store.one("SELECT description, comment, sensitive FROM cat_column WHERE table_name=? AND "
                                   "name=?", (h["table"], h["column"])) or {}
                entry.update(column=h["column"], column_about=c.get("description") or c.get("comment"),
                             protected=bool(c.get("sensitive")))
            schema.append(entry)
        values = [{k: v[k] for k in ("value", "table", "column", "freq")} for v in self.index.search_values(q, top=10)]
        return {"query": q, "knowledge": groups, "schema": schema, "values": values}

    def pinned(self, user: User) -> list[dict[str, Any]]:
        return [i for i in self.knowledge.visible(user, "example") if i["pinned"] and i["owner"] == user.id]

    def pin(self, user: User, turn_id: str) -> dict[str, Any]:
        """Pin one of your reports: your own example with the same SQL is flagged, or one is created
        (pinning your own report counts as confirming it for you)."""
        t = self._turn(user, turn_id)
        if t["kind"] != "report":
            raise ValueError("Only reports can be pinned.")
        canon = canonical_hash(t["sql"], self.target.dialect)
        item = next((i for i in self.knowledge.visible(user, "example")
                     if i["owner"] == user.id and i["sql_canonical"] == canon), None)
        if not item:
            item = self.knowledge._create(user=user, kind="example", title=json.loads(t["payload"])["title"],
                                          question=t["question"], sql=t["sql"], source_turn=turn_id, note="pinned")
        return self.knowledge.set_pinned(user, item["id"], True)

    def unpin(self, user: User, item_id: str) -> dict[str, Any]:
        return self.knowledge.set_pinned(user, item_id, False)

    def rerun(self, user: User, turn_id: str) -> dict[str, Any]:
        """"Re-run with today's data": an earlier report of yours, same SQL, fresh rows, no model call.
        Recorded as a new turn in the same conversation with usage.route = "rerun"."""
        t = self._turn(user, turn_id)
        if t["kind"] != "report":
            raise ValueError("Only reports can be re-run.")
        p = json.loads(t["payload"])
        res = self._run_report_sql(t["sql"])
        out = Report(title=p["title"], sql=t["sql"], assumptions=p.get("assumptions") or [],
                     follow_ups=p.get("follow_ups") or [])
        usage_d = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "tool_calls": 0,
                   "model": None, "escalated": False, "route": "rerun"}
        deps = Deps(app=self, user=user, trace=[{"tool": "rerun", "turn": turn_id}])
        return self._report_turn(new_id("turn"), t["conversation_id"], user, t["question"], out, res, deps, usage_d)

    def drill(self, user: User, turn_id: str, row: int, column: str | None = None) -> dict[str, Any]:
        """"Explain this number": the rows behind one row of a summary report of yours, built with
        sqlglot from the report's SQL (no model call), guarded, and recorded as a new turn (route "drill")."""
        t = self._turn(user, turn_id)
        if t["kind"] != "report":
            raise ValueError("Only reports can be drilled into.")
        p = json.loads(t["payload"])
        if not 0 <= row < len(p["rows"]) or (column is not None and column not in p["columns"]):
            raise ValueError("No such cell in this report.")
        sql, labels = drill_sql(t["sql"], self.target.dialect, p["columns"], p["rows"][row], self.catalog.schema,
                                self.catalog.sensitive)
        res = self._run_report_sql(sql)
        where = ", ".join(f"{k} = {v}" for k, v in labels)
        out = Report(title=f"{p['title']}: rows for {where}"[:120], sql=sql,
                     assumptions=[msg.say("drill_rows", title=p["title"], where=where)])
        usage_d = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "tool_calls": 0,
                   "model": None, "escalated": False, "route": "drill"}
        deps = Deps(app=self, user=user, trace=[{"tool": "drill", "turn": turn_id, "row": row}])
        return self._report_turn(new_id("turn"), t["conversation_id"], user, t["question"], out, res, deps, usage_d)

    def turn_csv(self, user: User, turn_id: str) -> str:
        import csv
        import io
        t = self._turn(user, turn_id)
        if t["kind"] != "report":
            raise ValueError("Only reports can be downloaded.")
        p = json.loads(t["payload"])
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(p["columns"])
        w.writerows(p["rows"])
        return buf.getvalue()

    def _check_item_sql(self, kind: str, sql: str | None) -> None:
        """Hand-written SQL is held to the same rules as the bot's: examples must run; joins must
        name two real table.column pairs; term predicates must work inside a WHERE clause."""
        if not sql:
            return
        if kind == "example":
            self.revalidate_check(sql)
        elif kind == "join":
            sides = [s.strip() for s in sql.split("=")]
            if len(sides) != 2 or not all("." in s for s in sides):
                raise ValueError("A join must look like table_a.column = table_b.column")
            for s in sides:
                t, c = s.split(".", 1)
                if c not in self.catalog.schema.get(t, {}):
                    raise ValueError(f"{s} is not a known column")
        elif kind == "term":
            tables = sorted({m.split(".")[0] for m in sql.replace("(", " ").split() if "." in m and m[0].isalpha()})
            if tables:
                self.revalidate_check(f"SELECT 1 FROM {', '.join(tables)} WHERE {sql}")

    def revalidate_check(self, sql: str) -> None:
        g = guard(sql, dialect=self.target.dialect, schema=self.catalog.schema, sensitive=self.catalog.sensitive,
                  allowed_tables=self.allowed_tables, row_cap=1)
        self.target.run(g.sql, max_rows=1)

    def edit_knowledge(self, user: User, item_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        item = self.knowledge.get(item_id)
        if not item:
            raise KeyError(item_id)
        if "sql" in changes:
            try:
                self._check_item_sql(item["kind"], changes["sql"])
            except Exception as e:
                raise ValueError(msg.say("edit_bad_sql", error=str(getattr(e, "orig", e))[:300])) from e
        o = self.knowledge.edit(user, item_id, changes)
        return {"message": msg.say(o.message, title=o.item["title"]), "item": o.item}

    def add_knowledge(self, user: User, *, kind: str, title: str, body: str | None = None, sql: str | None = None,
                      question: str | None = None, scope: str = "org") -> dict[str, Any]:
        try:
            self._check_item_sql(kind, sql)
        except Exception as e:
            raise ValueError(msg.say("edit_bad_sql", error=str(getattr(e, "orig", e))[:300])) from e
        o = self.knowledge.add(user, kind=kind, title=title, body=body, sql=sql, question=question, scope=scope)
        return {"message": msg.say(o.message, title=title), "item": o.item}

    def my_knowledge(self, user: User) -> dict[str, Any]:
        items = self.knowledge.mine(user)
        for i in items:
            i["label"] = msg.status_label(i["status"], i["scope"])
        shared = [i for i in self.knowledge.visible(user) if i["owner"] != user.id]
        for i in shared:
            i["label"] = msg.status_label(i["status"], i["scope"])
        stale = sum(1 for i in items if i["status"] == "stale")
        return {"mine": items, "shared": shared, "notice": msg.say("stale_notice", n=stale) if stale else None}

    def review_queue(self, user: User) -> list[dict[str, Any]]:
        if not user.is_admin:
            raise PermissionError("Only admins can see the review queue.")
        return self.knowledge.review_queue()
