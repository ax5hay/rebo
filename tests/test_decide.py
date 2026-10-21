"""Doubt-gated decide (docs/20 §5b): the cheap agent model answers; when it wants to ask (or a check
fires) the decide model settles the turn from its lookups. Scripted models, no LLM."""
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from rebo.agent import build_agent
from rebo.knowledge import User


async def test_the_decide_model_answers_from_the_explorers_lookups(app):
    def explorer(messages, info):
        if not any(isinstance(p, ToolReturnPart) for m in messages for p in m.parts):
            return ModelResponse(parts=[ToolCallPart("search_values", {"text": "paused"})])
        return ModelResponse(parts=[ToolCallPart("ask_clarifying_question", {
            "why": "Paused could mean two things.", "questions": [{"question": "Which?", "options": ["a", "b"]}]})])
    seen = []

    def decider(messages, info):
        seen.append(messages[-1].parts[-1].content)
        return ModelResponse(parts=[ToolCallPart("present_report", {
            "title": "Paused customers", "sql": "SELECT full_name AS customer FROM customer WHERE status = 'paused'",
            "assumptions": ["Paused means the status is paused."]})])
    app.settings.decide_model = "openrouter:anthropic/claude-opus-5.5"
    app.__dict__.update(agent=build_agent(FunctionModel(explorer)), decide_model=FunctionModel(decider),
                        escalation_model=None)
    r = await app.ask(User("ada"), "paused customers")
    assert r["kind"] == "report" and r["title"] == "Paused customers"
    assert "search_values" in seen[0] and "paused" in seen[0]
    assert "<draft>" in seen[0] and "Paused could mean two things." in seen[0]
    usage = app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"]
    assert '"decided_for": "clarify"' in usage and '"before"' in usage


async def test_a_confident_report_never_reaches_the_decide_model(app):
    sql = "SELECT full_name AS customer FROM customer WHERE status = 'paused'"
    calls = []
    app.settings.decide_model = "openrouter:anthropic/claude-opus-5.5"
    app.__dict__.update(agent=build_agent(FunctionModel(lambda m, i: ModelResponse(parts=[ToolCallPart(
        "present_report", {"title": "Paused", "sql": sql, "assumptions": []})]))),
        decide_model=FunctionModel(lambda m, i: calls.append(1)), escalation_model=None)
    r = await app.ask(User("ada"), "paused customers")
    assert r["kind"] == "report" and calls == []
