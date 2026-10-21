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
import sqlglot
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlglot import exp

DB_URL = os.environ.get("MOCK_JMS_DATABASE_URL", "mysql+pymysql://reports_ro:reports_ro@127.0.0.1:3307/jms")
_ALLOWED_OPS = (exp.EQ, exp.NEQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Is, exp.Like)
_REJECTED = (exp.With, exp.Union, exp.Intersect, exp.Except, exp.Distinct, exp.Group, exp.Having, exp.Order,
             exp.Case, exp.In, exp.Between, exp.Or, exp.Subquery, exp.Window)


def builder_grammar_problem(sql: str) -> str | None:
    """Approximates the staging Report Builder reader (orchid/utils/report_query.py
    translate_sql_to_query_dict): one flat SELECT, plain or aliased columns, INNER/LEFT joins,
    AND-ed simple filters, no functions except LOWER(col) LIKE. None = editable."""
    try:
        tree = sqlglot.parse_one(sql, read="mysql")
    except Exception as e:
        return f"does not parse: {e}"
    if not isinstance(tree, exp.Select):
        return "not a single SELECT"
    for node in tree.walk():
        if isinstance(node, _REJECTED):
            return f"{node.key.upper()} is not supported by the Report Builder"
        if (isinstance(node, exp.Not) and isinstance(node.this, exp.Like)) or (
                isinstance(node, exp.Like) and node.args.get("negate")):  # sqlglot 30: Like(negate=True)
            return "NOT LIKE is not supported"
        if isinstance(node, exp.Func) and not isinstance(node, (exp.Lower, *_ALLOWED_OPS, exp.And, exp.Not)):
            if not isinstance(node, (exp.Column, exp.Literal, exp.Star)):
                return f"function {node.sql_name()} is not supported"
    for j in tree.args.get("joins") or []:
        if (j.side or "").upper() not in ("", "LEFT") or (j.kind or "").upper() not in ("", "INNER", "OUTER"):
            return f"{j.side} {j.kind} JOIN is not supported"
    for col in tree.expressions:
        inner = col.this if isinstance(col, exp.Alias) else col
        if not isinstance(inner, exp.Column):
            return "only plain columns can be selected"
    return None


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


@app.get("/mock/health")
def health():
    return {"ok": True, "reports": len(_reports)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("MOCK_JMS_PORT", "8090")))
