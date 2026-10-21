"""Contract replay (B-040): every reports.action through the JMS adapter, requests validated against the
captured ChatMessageRequest schema and every response against ChatResponse
(fixtures/jms_contract/chat_contract.schema.json)."""
import json
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from rebo.agent import build_agent
from rebo.api import create_app
from test_jms_adapter import SECRET, token

SCHEMA = json.loads((Path(__file__).parents[1] / "fixtures" / "jms_contract" / "chat_contract.schema.json")
                    .read_text(encoding="utf-8"))
ACTIONS = SCHEMA["ReportsInteraction"]["$defs"]["ReportsUserAction"]["enum"]


def model(messages, info):
    prompt = [p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart)][-1].lower()
    if "<request>customers</request>" in prompt:
        return ModelResponse(parts=[ToolCallPart("ask_clarifying_question", {"why": "Several statuses.",
                             "questions": [{"question": "Which customers?", "options": ["paused", "closed"]}]})])
    status = "closed" if "closed" in prompt.split("<request>")[-1] else "paused"
    return ModelResponse(parts=[ToolCallPart("present_report", {
        "title": f"{status} customers", "assumptions": [], "follow_ups": ["Closed ones too"],
        "learnable": [{"kind": "term", "title": "on hold", "body": "status paused"}],
        "sql": f"SELECT full_name AS customer FROM customer WHERE status = '{status}'"})])


@pytest.fixture()
def chat(app, monkeypatch):
    monkeypatch.setenv("REBO_JWT_SECRET", SECRET)
    app.settings.auth_mode, app.settings.adapters, app.settings.jwt_secret = "jwt", ["jms"], SECRET
    app.__dict__["agent"] = build_agent(FunctionModel(model))
    client = TestClient(create_app(app, with_ui=False))
    seen = []

    def send(message="", **reports):
        body = {"message": message, "session": {"contact_id": 0}, "context": {}, "reports": reports}
        jsonschema.validate(body, SCHEMA["ChatMessageRequest"])
        r = client.post("/api/v1/chat/0", headers=token(), json=body)
        assert r.status_code == 200, r.text
        jsonschema.validate(r.json(), SCHEMA["ChatResponse"])
        seen.append(reports.get("action", "query"))
        return r.json()

    send.seen = seen
    return send


def test_every_reports_action_returns_a_valid_chat_response(chat):
    first = chat("customers", action="new_report")
    sid = first["reports_session_id"]
    assert first["reports_phase"] == "clarify"
    answer = next(o for o in first["reports_options"] if o["label"] == "closed")
    report = chat("", action="select_option", option_id=answer["option_id"], reports_session_id=sid)
    assert report["reports_phase"] == "result" and report["row_count"] == 10
    ids = [o["option_id"] for o in report["reports_options"]]
    chat("", action="select_option", option_id="confirm", reports_session_id=sid)
    chat("", action="select_option", option_id=next(i for i in ids if i.startswith("remember:")), reports_session_id=sid)
    chat("", action="select_option", option_id="followup:0", reports_session_id=sid)
    chat("", action="confirm", reports_session_id=sid)
    chat("only the paused ones", action="reject", reports_session_id=sid)
    corrected = chat("only the paused ones", action="freetext", reports_session_id=sid)
    assert corrected["reports_phase"] == "result"
    chat("paused customers", action="manual_select", reports_session_id=sid)
    chat("paused customers", action="query", reports_session_id=sid)
    resumed = chat("", action="resume", reports_session_id=sid)
    assert resumed["reports_phase"] == "result"
    assert set(chat.seen) == set(ACTIONS)
