"""Mock JMS host: everything the bot touches on the JMS side, with no RDS and no JMS code.

    uv run python mocks/jms/server.py            # http://127.0.0.1:8090

Endpoints (each mirrors a real JMS behaviour; docs/18-production-build.md §4 maps them):
  POST /mock/token                  mint the HS256 JWT JMS gives the chat widget (iss=orchid, bot_type=reports)
  GET  /mock/admins                 admin directory for the reports admin picker (from the local DB)
  POST /mock/custom-reports         save a bot report like admin_reports_chat.report_action does:
                                    report_query = SQL, editable = passes the Report Builder grammar check
  GET  /mock/custom-reports/{id}    the saved definition
  GET  /mock/custom-reports/{id}/run  live re-run on open (JMS executes report_query every time)

Environment: REPORTSBOT_JWT_SECRET (shared with the bot), MOCK_JMS_DATABASE_URL (default: the local
read-only test DB).
"""
from __future__ import annotations

import itertools
import os
import time

import jwt
from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel
from sqlalchemy import create_engine, text

from reportsbot.adapters.jms import builder_grammar_problem  # the same check the bot's guard uses (B-038)

DB_URL = os.environ.get("MOCK_JMS_DATABASE_URL", "mysql+pymysql://reports_ro:reports_ro@127.0.0.1:3307/jms")
class TokenIn(BaseModel):
    user_id: int
    role: str = "user"          # user | admin (JMS would derive this from admin permissions)
    tenant_id: int = 1
    db_schema: str = "jms"
    user_type: str = "admin"


class ReportIn(BaseModel):
    title: str
    sql: str
    created_by: int | None = None


app = FastAPI(title="mock-jms")
_reports: dict[int, dict] = {}
_ids = itertools.count(1)


def _engine():
    return create_engine(DB_URL, pool_pre_ping=True)


@app.post("/mock/token")
def token(body: TokenIn):
    secret = os.environ.get("REPORTSBOT_JWT_SECRET")
    if not secret:
        raise HTTPException(500, "REPORTSBOT_JWT_SECRET is not set")
    now = int(time.time())
    claims = {"iss": "orchid", "bot_type": "reports", "sub": str(body.user_id), "user_id": body.user_id,
              "user_type": body.user_type, "role": body.role, "tenant_id": body.tenant_id,
              "db_schema": body.db_schema, "subdomain": body.db_schema, "region": "local",
              "iat": now, "exp": now + 3600}
    return {"token": jwt.encode(claims, secret, algorithm="HS256"), "claims": claims}


@app.get("/mock/admins")
def admins():
    with _engine().connect() as c:
        rows = c.execute(text("SELECT admin_id, first_name, last_name FROM admin ORDER BY last_name LIMIT 200"))
        return [{"admin_id": a, "name": f"{f} {l}"} for a, f, l in rows]


@app.post("/mock/custom-reports")
def save_report(body: ReportIn):
    problem = builder_grammar_problem(body.sql)
    rid = next(_ids)
    _reports[rid] = {"custom_report_id": rid, "report_title": body.title, "report_query": body.sql,
                     "query_dict": None, "editable": problem is None, "uneditable_reason": problem,
                     "created_by": body.created_by, "created": time.time()}
    return _reports[rid]


@app.get("/mock/custom-reports/{rid}")
def get_report(rid: int):
    if rid not in _reports:
        raise HTTPException(404, "no such report")
    return _reports[rid]


@app.get("/mock/custom-reports/{rid}/run")
def run_report(rid: int):
    rep = get_report(rid)
    with _engine().connect() as c:
        res = c.execute(text(rep["report_query"].replace(":", r"\:")))
        rows = [list(map(str, r)) for r in res.fetchmany(500)]
        return {"columns": list(res.keys()), "rows": rows, "row_count": len(rows)}


# Asynchronous answers. In JMS the bot's message goes through SQS to the WebSocket service, which
# sends {"type": "reports.ready", "payload": <ChatResponse>} to the user's browser (README §3).
# Point the bot's notify_url at /mock/sqs; a client reads its pushes from /mock/ws/{user_id}.
_pushed: dict[str, list[dict]] = {}


@app.post("/mock/sqs")
def sqs(event: dict):
    if event.get("event") == "report_ready" and (event.get("deliver") or {}).get("kind") == "jms":
        _pushed.setdefault(str(event["user"]), []).append({"type": "reports.ready", "payload": event["response"]})
    return {"ok": True}


@app.websocket("/mock/ws/{user_id}")
async def push(websocket: WebSocket, user_id: str):
    await websocket.accept()
    for message in _pushed.pop(user_id, []):
        await websocket.send_json(message)
    await websocket.close()


@app.get("/mock/health")
def health():
    return {"ok": True, "reports": len(_reports)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("MOCK_JMS_PORT", "8090")))
