import json

import httpx2 as httpx  # Pydantic AI 2.x injects httpx2 clients into OpenAI-compatible providers
import pytest
from pydantic_ai.models.fallback import FallbackModel

from reportsbot.agent import build_agent
from reportsbot.knowledge import User
from reportsbot.llm import build_model, parse


def test_parse_prefixes_and_openrouter_shorthand():
    assert parse("google:gemini-x") == ("google", "gemini-x")
    assert parse("lmstudio:qwen/qwen3-coder") == ("lmstudio", "qwen/qwen3-coder")
    assert parse("anthropic/claude-sonnet-5.5") == ("openrouter", "anthropic/claude-sonnet-5.5")
    with pytest.raises(ValueError):
        parse("gemini-x")


def test_every_provider_builds_offline(app, monkeypatch):
    for k in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(k, "test")
    names = {type(build_model(s, app.settings)).__name__ for s in
             ("openrouter:anthropic/claude-sonnet-5.5", "anthropic:claude-sonnet-5-5", "google:gemini-x",
              "lmstudio:local-model", "openai:gpt-x")}
    assert names == {"OpenRouterModel", "AnthropicModel", "GoogleModel", "OpenAIChatModel"}
    fb = build_model("openrouter:anthropic/claude-sonnet-5.5", app.settings, ["google:gemini-x", "lmstudio:m"])
    assert isinstance(fb, FallbackModel)


def _completion(name: str, args: dict) -> dict:
    return {"id": "c", "object": "chat.completion", "created": 0, "model": "local-model",
            "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "t1", "type": "function",
                                "function": {"name": name, "arguments": json.dumps(args)}}]}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


async def test_all_open_questions_come_back_in_one_clarify_turn(app):
    payload = {"why": "The two readings give different lists.", "questions": [
        {"question": "Which customers?", "options": ["active", "paused"]},
        {"question": "Which date?", "options": ["created", "last order"]}]}

    def handler(request):
        return httpx.Response(200, json=_completion("ask_clarifying_question", payload))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app.__dict__["agent"] = build_agent(build_model("lmstudio:m", app.settings, http_client=client))
    r = await app.ask(User("alice"), "good customers by date")
    assert r["kind"] == "clarify" and [q["question"] for q in r["questions"]] == ["Which customers?", "Which date?"]


async def test_lmstudio_wire_protocol_end_to_end(app):
    """A stand-in for LM Studio's OpenAI-compatible server: one tool call, then a validated report."""
    seen = []
    script = [
        _completion("search_values", {"text": "paused"}),
        _completion("present_report", {"title": "Paused customers",
                                       "sql": "SELECT full_name AS customer FROM customer WHERE status = 'paused'",
                                       "assumptions": ["Paused means the stored status 'paused'."]}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=script[min(len(seen) - 1, len(script) - 1)])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app.__dict__["agent"] = build_agent(build_model("lmstudio:local-model", app.settings, http_client=client))
    r = await app.ask(User("alice"), "paused customers")
    assert all(u.startswith(app.settings.lmstudio_url) and u.endswith("/chat/completions") for u in seen)
    assert r["kind"] == "report" and len(r["rows"]) == 10
    assert [t["tool"] for t in r["trace"]] == ["search_values"]
