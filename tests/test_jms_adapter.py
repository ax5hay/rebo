"""JMS contract through the adapter, with JMS mocked (no RDS, no JMS code, no LLM)."""
import json
import re
import sys
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient

from reportsbot.agent import build_agent
from reportsbot.api import create_app
from reportsbot.knowledge import User
from reportsbot.llm import build_model

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mocks" / "jms"))
import server as mock_jms  # noqa: E402

SECRET = "test-secret-with-at-least-32-bytes!!"
REPORT = {"title": "Paused customers", "sql": "SELECT full_name AS customer FROM customer WHERE status = 'paused'",
          "assumptions": ["Paused means status paused."], "follow_ups": ["Paused customers by month"],
          "learnable": [{"kind": "term", "title": "paused", "body": "status is paused", "sql": "customer.status = 'paused'"}]}


def _completion(name, args):
    return {"id": "c", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None,
                         "tool_calls": [{"id": "t", "type": "function",
                                         "function": {"name": name, "arguments": json.dumps(args)}}]}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


@pytest.fixture()
def client(app, monkeypatch):
    monkeypatch.setenv("REPORTSBOT_JWT_SECRET", SECRET)
    app.settings.auth_mode, app.settings.adapters, app.settings.jwt_secret = "jwt", ["jms"], SECRET
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(
        lambda req: httpx2.Response(200, json=_completion("present_report", REPORT))))
    app.__dict__["agent"] = build_agent(build_model("lmstudio:m", app.settings, http_client=http))
    return TestClient(create_app(app, with_ui=False))


def token(user_id=7, role="member", bot_type="reports"):
    t = mock_jms.token(mock_jms.TokenIn(user_id=user_id, role=role))["token"]
    if bot_type != "reports":
        import jwt
        claims = jwt.decode(t, SECRET, algorithms=["HS256"])
        t = jwt.encode({**claims, "bot_type": bot_type}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {t}"}


def test_jms_chat_contract_report_confirm_and_remember(client, app):
    r = client.post("/api/v1/chat/0", headers=token(), json={"message": "paused customers", "reports": {"action": "query"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sql"] and body["row_count"] == 10 and body["reports_phase"] == "result"
    ids = [o["option_id"] for o in body["reports_options"]]
    assert ids[:3] == ["confirm", "reject", "followup:0"] and ids[3].startswith("remember:")
    sid = body["reports_session_id"]

    c = client.post("/api/v1/chat/0", headers=token(),
                    json={"message": "", "reports": {"action": "select_option", "option_id": "confirm", "reports_session_id": sid}})
    assert "only tunes the bot for you" in c.json()["message"]
    m = client.post("/api/v1/chat/0", headers=token(),
                    json={"message": "", "reports": {"action": "select_option", "option_id": ids[3], "reports_session_id": sid}})
    assert "Only you are affected" in m.json()["message"]
    assert {i["kind"] for i in app.knowledge.mine(User("7"))} == {"example", "term"}


def test_jwt_rules(client):
    assert client.post("/api/v1/chat/0", json={"message": "x"}).status_code == 422  # no Authorization header
    assert client.post("/api/v1/chat/0", headers={"Authorization": "Bearer junk"}, json={"message": "x"}).status_code == 401
    assert client.post("/api/v1/chat/0", headers=token(bot_type="intake"), json={"message": "x"}).status_code == 403


def test_core_api_uses_jwt_identity_when_configured(client):
    assert client.get("/api/knowledge", headers={"X-User-Id": "7"}).status_code == 422
    assert client.get("/api/knowledge", headers=token(user_id=7)).status_code == 200
    assert client.get("/api/review", headers=token(role="curator")).status_code == 200
    assert client.get("/api/review", headers=token(role="member")).status_code == 403


@pytest.mark.parametrize("sql,problem", [
    ("SELECT g.case_id, c.first_name AS f FROM gc_case g LEFT JOIN contact c ON c.contact_id = g.gc_id "
     "WHERE g.stage = 'intake' AND g.active = 1", None),
    ("SELECT case_id FROM gc_case WHERE lower(case_file_name) LIKE '%smith%'", None),
    ("SELECT case_id FROM gc_case ORDER BY case_id", "ORDER"),
    ("SELECT DISTINCT case_id FROM gc_case", "DISTINCT"),
    ("SELECT COUNT(*) FROM gc_case", "COUNT"),
    ("SELECT case_id FROM gc_case WHERE stage IN ('a','b')", "IN"),
    ("SELECT case_id FROM gc_case WHERE stage = 'a' OR stage = 'b'", "OR"),
    ("SELECT case_id FROM gc_case WHERE case_file_name NOT LIKE '%x%'", "NOT LIKE"),
])
def test_mock_builder_grammar(sql, problem):
    got = mock_jms.builder_grammar_problem(sql)
    assert (got is None) if problem is None else (got and re.search(problem, got))
