"""JMS adapter: speaks the chat contract the JMS frontend already uses for the reports bot, so
JMS can switch to this bot without frontend changes. Enable with `adapters: [jms]` and
`auth.mode: jwt` (JMS signs HS256 tokens with iss="orchid").

Contract (from the current JMS integration, backend/app/models/domain/{rag,reports}.py):
  POST /api/v1/chat/{contact_id}   Authorization: Bearer <JWT with bot_type="reports">
  body     {"message": str, "reports": {"action": query|freetext|select_option|confirm|reject|new_report,
            "option_id": str|null, "reports_session_id": str|null}, ...ignored JMS fields}
  response {"contact_id", "message", "sql", "columns", "rows", "row_count", "truncated", "error",
            "reports_phase", "reports_session_id", "reports_awaiting", "reports_options": [ReportOption],
            "reports_allow_freetext", "reports_freetext_prompt"}

Mapping: reports_session_id = conversation id. A report answer offers options confirm / reject /
follow-ups / remember-this; a clarification offers its options (questions flattened as "Q → A").
See docs/10-api-and-ui.md §5 and docs/18-production-build.md.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..api import decode_jwt, user_from_claims
from ..knowledge import User
from ..service import App, RateLimited
from ..store import new_id


class ReportsInteraction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    action: str = "query"
    option_id: str | None = None
    reports_session_id: str | None = None
    # Answer in the background and push the ChatResponse as {"type": "reports.ready"} (README §3).
    run_async: bool = Field(False, alias="async")


class ChatIn(BaseModel):
    message: str = ""
    reports: ReportsInteraction | None = None


def _option(option_id: str, label: str, description: str = "", sql: str = "") -> dict[str, Any]:
    return {"option_id": option_id, "label": label, "description": description, "sql": sql, "explanation": ""}


def to_jms(contact_id: int, r: dict[str, Any]) -> dict[str, Any]:
    """Bot payload -> JMS ChatResponse fields."""
    base = {"contact_id": contact_id, "reports_session_id": r.get("conversation_id"),
            "reports_allow_freetext": True, "sql": None, "columns": [], "rows": [], "row_count": None,
            "truncated": None, "error": None, "reports_options": []}
    kind = r.get("kind")
    if kind == "report":
        opts = [_option("confirm", "Yes, this is right"), _option("reject", "No, fix it")]
        opts += [_option(f"followup:{i}", f) for i, f in enumerate(r.get("follow_ups") or [])]
        opts += [_option(f"remember:{s['id']}", f"Remember: {s['title']}", s["body"]) for s in r.get("suggestions") or []]
        text = "\n".join([r["provenance"]["text"], r["message"], "How I read your question:",
                          *[f"- {a}" for a in r["assumptions"]]])
        return {**base, "message": text, "sql": r["sql"], "columns": r["columns"], "rows": r["rows"],
                "row_count": len(r["rows"]), "truncated": r["truncated"], "reports_phase": "result",
                "reports_awaiting": "selection", "reports_options": opts,
                "reports_freetext_prompt": "Ask a follow-up, or describe what should change."}
    if kind == "clarify":
        many = len(r["questions"]) > 1
        opts = [_option(f"answer:{qi}:{oi}", f"{q['question']} → {o}" if many else o)
                for qi, q in enumerate(r["questions"]) for oi, o in enumerate(q["options"])]
        text = "\n".join([r["intro"], *[q["question"] for q in r["questions"]], r["why"]])
        return {**base, "message": text, "reports_phase": "clarify", "reports_awaiting": "selection",
                "reports_options": opts,
                "reports_freetext_prompt": "Or type your answer" + (" to each question" if many else "")}
    if kind == "answer":
        return {**base, "message": r["text"], "reports_phase": "answer", "reports_awaiting": "freetext"}
    return {**base, "message": r.get("message", ""), "error": r.get("message"), "reports_phase": "error",
            "reports_awaiting": "freetext"}


def router(app: App) -> APIRouter:
    r = APIRouter()
    # Background answers (jobs.py) reach JMS through notify_url as report_ready with this ChatResponse.
    app.deliver_formatters["jms"] = lambda deliver, result: to_jms(deliver["contact_id"], result)

    def last_turn(user: User, conversation_id: str | None, kind: str | None = None) -> dict[str, Any]:
        sql = "SELECT * FROM turn WHERE conversation_id=? AND owner=?" + (" AND kind=?" if kind else "")
        args = (conversation_id, user.id) + ((kind,) if kind else ())
        row = app.store.one(sql + " ORDER BY created_at DESC LIMIT 1", args)
        if not row:
            raise HTTPException(400, "No earlier answer in this reports session.")
        return row

    @r.post("/api/v1/chat/{contact_id}")
    async def chat(contact_id: int, body: ChatIn, authorization: str = Header(...)):
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing Bearer token")
        claims = decode_jwt(authorization.removeprefix("Bearer ").strip(), app.settings)
        if str(claims.get("bot_type", "")).lower() != "reports":
            raise HTTPException(403, "This endpoint serves bot_type=reports only")
        user = user_from_claims(claims)
        it = body.reports or ReportsInteraction()
        conv = None if it.action == "new_report" else it.reports_session_id
        action, opt = it.action, it.option_id or ""
        if action in ("confirm", "reject") or opt in ("confirm", "reject"):
            verdict = "correct" if "confirm" in (action, opt) else "wrong"
            res = app.feedback(user, last_turn(user, conv, "report")["id"], verdict, body.message)
            awaiting = "freetext" if verdict == "wrong" else "selection"
            return {"contact_id": contact_id, "message": res["message"], "reports_session_id": conv,
                    "reports_phase": "feedback", "reports_awaiting": awaiting, "reports_options": [],
                    "reports_allow_freetext": True, "columns": [], "rows": []}
        if opt.startswith("remember:"):
            res = app.remember(user, opt.split(":", 1)[1], True)
            return {"contact_id": contact_id, "message": res["message"], "reports_session_id": conv,
                    "reports_phase": "feedback", "reports_awaiting": "freetext", "reports_options": [],
                    "reports_allow_freetext": True, "columns": [], "rows": []}
        text = body.message
        if opt.startswith(("answer:", "followup:")):
            prev = json.loads(last_turn(user, conv)["payload"])
            if opt.startswith("answer:"):
                qi, oi = map(int, opt.split(":")[1:])
                q = prev["questions"][qi]
                text = f"{q['question']} → {q['options'][oi]}"
            else:
                text = prev["follow_ups"][int(opt.split(":")[1])]
        elif last := (app.store.one("SELECT feedback FROM turn WHERE conversation_id=? AND owner=? AND kind='report' "
                                     "ORDER BY created_at DESC LIMIT 1", (conv, user.id)) if conv else None):
            if last["feedback"] == "wrong" and action in ("freetext", "query"):
                text = f"Correction to the previous report: {text}"
        if not text.strip():
            raise HTTPException(400, "Empty message")
        if it.run_async:
            conv = conv or new_id("conv")
            if (c := app.store.one("SELECT owner FROM conversation WHERE id=?", (conv,))) and c["owner"] != user.id:
                raise HTTPException(403, "That conversation belongs to someone else.")
            job = app.jobs.enqueue("ask", user, {"text": text, "conversation_id": conv,
                                                 "deliver": {"kind": "jms", "contact_id": contact_id}})
            return {"contact_id": contact_id, "message": "Working on it; the report will appear here.",
                    "reports_session_id": conv, "reports_phase": "working", "reports_awaiting": "none",
                    "reports_options": [], "reports_allow_freetext": False, "columns": [], "rows": [],
                    "job_id": job}
        try:
            return to_jms(contact_id, await app.ask(user, text, conv))
        except PermissionError as e:
            raise HTTPException(403, str(e)) from e
        except RateLimited as e:
            raise HTTPException(429, str(e)) from e

    return r
