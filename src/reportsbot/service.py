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
from pydantic_ai import Agent, ModelMessage, ModelMessagesTypeAdapter, ModelRetry, UsageLimitExceeded, UsageLimits
from pydantic_ai.messages import ModelRequest, UserPromptPart

from . import messages as msg
from .agent import Clarify, Deps, Report, Reply, build_agent
from .catalog import Catalog, bootstrap
from .knowledge import Knowledge, User
from .llm import build_model, credentials_present
from .observability import setup_tracing
from .retrieval import Index, get_embedder
from .safety import canonical_hash, guard
from .settings import Settings, get_settings
from .store import Store, new_id, now
from .target import TargetDB

log = logging.getLogger(__name__)
_KEEP_RUNS = 4  # earlier user turns kept in the model's message history


class ColumnDoc(BaseModel):
    name: str
    meaning: str = Field(description="Short meaning, grounded in the name, type, statistics and sample values")


class TableDoc(BaseModel):
    table: str = Field(description="One or two sentences: what one row of this table represents and what it is used for")
    columns: list[ColumnDoc] = Field(default_factory=list, description=(
        "Every column whose name is not self-explanatory: abbreviations, codes, flags, statuses, "
        "ids pointing to other tables, dates with a specific business meaning. Skip only obvious ones "
        "like created, updated, first_name."))


class App:
    def __init__(self, settings: Settings | None = None):
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
        return build_agent(build_model(s.model, s, s.fallback_models))

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

    def _context_block(self, user: User, text: str) -> str:
        items = self.knowledge.search(user, text, top=6)
        hits = self.index.search_schema(text, top=20)
        tables = list(dict.fromkeys(h["table"] for h in hits))[:8]
        values = self.index.search_values(text, top=8)
        parts = ["<learned_knowledge>"]
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
                    "text": msg.say("prov_verified", who=verified["verified_by"] or "a curator", when=when)}
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
        deps = Deps(app=self, user=user)
        turn_id = new_id("turn")
        limits = UsageLimits(request_limit=40, tool_calls_limit=self.settings.max_tool_calls)
        prompt = self._context_block(user, text)
        escalated = False
        try:
            try:
                result = await self.agent.run(prompt, deps=deps, message_history=history, usage_limits=limits)
            except Exception as first:
                # Cost cascade: the cheap model failed (SQL never validated, budget, API error) ->
                # one retry on the stronger escalation model, from a clean slate.
                if not self.escalation_model:
                    raise
                log.info("escalating after %s: %s", type(first).__name__, str(first)[:200])
                deps = Deps(app=self, user=user, trace=[*deps.trace, {"tool": "escalate", "after": type(first).__name__}])
                escalated = True
                result = await self.agent.run(prompt, deps=deps, message_history=history, usage_limits=limits,
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
                   "model": self.settings.escalate_model if escalated else self.settings.model, "escalated": escalated}
        if isinstance(out, Report) and deps.final is not None:
            prov = self._provenance(user, out.sql, out.used_knowledge)
            self.knowledge.mark_used(prov["item_ids"])
            res = deps.final
            payload = {"title": out.title, "sql": out.sql, "columns": res.columns, "rows": res.rows,
                       "truncated": res.truncated, "elapsed_ms": res.elapsed_ms, "assumptions": out.assumptions,
                       "provenance": prov, "follow_ups": out.follow_ups,
                       "message": msg.say("report_ready", title=out.title,
                                          row_phrase=msg.rows_phrase(len(res.rows), res.truncated)),
                       "suggestions": self._suggestions(user, turn_id, out.learnable)}
            return self._record(turn_id, conv_id, user, text, "report", payload, deps, sql=out.sql, prov=prov,
                                usage=usage_d)
        if isinstance(out, Clarify):
            payload = {"intro": msg.say("clarify_intro"), "why": out.why,
                       "questions": [q.model_dump() for q in out.questions]}
            return self._record(turn_id, conv_id, user, text, "clarify", payload, deps, usage=usage_d)
        reply = out if isinstance(out, Reply) else Reply(text=str(out))
        payload = {"text": reply.text, "suggestions": self._suggestions(user, turn_id, reply.learnable)}
        return self._record(turn_id, conv_id, user, text, "answer", payload, deps, usage=usage_d)

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
        with self.store.tx() as db:
            db.execute("UPDATE turn SET feedback=? WHERE id=?", (verdict, turn_id))
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
        outcomes = self.knowledge.reject(user, prov.get("item_ids", []), note)
        texts = [msg.say(o.message) for o in outcomes]
        return {"message": " ".join([*texts, msg.say("fix_prompt")]), "items": [o.item for o in outcomes],
                "next": "correction"}

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
        return {"message": msg.say("restored", title=o.item["title"],
                                   status=msg.status_label(o.item["status"], o.item["scope"]).lower()),
                "item": o.item}

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
        if not user.is_curator:
            raise PermissionError("Only curators can see the review queue.")
        return self.knowledge.review_queue()
