import json

import httpx2 as httpx  # Pydantic AI 2.x injects httpx2 clients into OpenAI-compatible providers
import pytest
from pydantic_ai.models.fallback import FallbackModel

from rebo.agent import build_agent
from rebo.knowledge import User
from rebo.llm import build_model, parse


def test_parse_prefixes_and_openrouter_shorthand():
    assert parse("google:gemini-x") == ("google", "gemini-x")
    assert parse("lmstudio:local/model-7b") == ("lmstudio", "local/model-7b")
    assert parse("anthropic/claude-sonnet-5.5") == ("openrouter", "anthropic/claude-sonnet-5.5")
    with pytest.raises(ValueError):
        parse("gemini-x")


def test_every_provider_builds_offline(app, monkeypatch):
    for k in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(k, "test")
    unwrap = lambda m: getattr(m, "wrapped", m)  # noqa: E731  (remote models come wrapped in PatientModel)
    names = {type(unwrap(build_model(s, app.settings))).__name__ for s in
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


async def test_failed_turn_escalates_once_to_the_stronger_model(app):
    bad = _completion("present_report", {"title": "x", "sql": "SELECT nope FROM customer", "assumptions": []})
    good = _completion("present_report", {"title": "Paused", "assumptions": [],
                                          "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})
    cheap = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=bad)))
    strong = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=good)))
    app.__dict__["agent"] = build_agent(build_model("lmstudio:cheap", app.settings, http_client=cheap))
    app.__dict__["escalation_model"] = build_model("lmstudio:strong", app.settings, http_client=strong)
    app.settings.escalate_model = "lmstudio:strong"
    r = await app.ask(User("alice"), "paused customers")
    assert r["kind"] == "report" and len(r["rows"]) == 10
    assert r["trace"][0]["tool"] == "escalate"
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert usage["escalated"] is True and usage["model"] == "lmstudio:strong"


async def test_trusted_saved_example_routes_to_fast_model_new_questions_to_agent_model(app):
    good = _completion("present_report", {"title": "Paused", "assumptions": [],
                                          "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})
    calls = {"fast": 0, "big": 0, "params": 0}
    not_same = _completion("fill_parameters", {"same_report": False, "values": []})

    def client(name):
        def handler(req):
            if "fill_parameters" in req.content.decode():   # the value-only check runs first on a reuse hit
                calls["params"] += 1
                return httpx.Response(200, json=not_same)
            calls[name] += 1
            return httpx.Response(200, json=good)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    app.settings.model, app.settings.fast_model = "lmstudio:big", "lmstudio:fast"
    app.__dict__["agent"] = build_agent(build_model("lmstudio:big", app.settings, http_client=client("big")))
    app.__dict__["fast_agent_model"] = build_model("lmstudio:fast", app.settings, http_client=client("fast"))
    alice, bob = User("alice"), User("bob")
    first = await app.ask(alice, "show the paused customers")          # nothing saved yet -> agent model
    app.feedback(alice, first["turn_id"], "correct")
    again = await app.ask(alice, "paused customers please show")       # trusted own example -> fast model
    other = await app.ask(bob, "show the paused customers")            # bob cannot see alice's item -> agent model
    route = lambda r: json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])["route"]
    assert [route(first), route(again), route(other)] == ["new", "reuse", "new"]
    assert calls == {"fast": 1, "big": 2, "params": 1}


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


FAN_OUT = ("SELECT c.customer_id, c.full_name AS customer, o.amount FROM customer c "
           "JOIN orders o ON o.customer_id = c.customer_id")


def _scripted(app, script):
    """Agent whose model returns `script` in order (last one repeats); returns the request bodies."""
    seen = []

    def handler(request):
        seen.append(request.content.decode())
        return httpx.Response(200, json=script[min(len(seen) - 1, len(script) - 1)])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app.__dict__["agent"] = build_agent(build_model("lmstudio:m", app.settings, http_client=client))
    return seen


async def test_fan_out_report_gets_one_grain_retry_then_the_fix_is_accepted(app):
    fixed = ("SELECT c.customer_id, c.full_name AS customer, SUM(o.amount) AS total FROM customer c "
             "JOIN orders o ON o.customer_id = c.customer_id GROUP BY c.customer_id, c.full_name")
    seen = _scripted(app, [_completion("present_report", {"title": "Spend", "sql": FAN_OUT, "assumptions": []}),
                           _completion("present_report", {"title": "Spend", "sql": fixed, "assumptions": []})])
    r = await app.ask(User("alice"), "customers and what they spent")
    assert r["kind"] == "report" and len(r["rows"]) == 40
    assert len(seen) == 2 and "rows repeat per customer" in seen[1]


async def test_deliberate_one_row_per_child_passes_on_the_second_attempt(app):
    again = {"title": "Orders by customer", "sql": FAN_OUT, "assumptions": ["One row per order is intended."]}
    seen = _scripted(app, [_completion("present_report", {**again, "assumptions": []}),
                           _completion("present_report", again)])
    r = await app.ask(User("alice"), "every order with its customer")
    assert r["kind"] == "report" and len(seen) == 2


async def test_no_grain_retry_when_the_entity_key_is_unique(app):
    sql = "SELECT o.order_id, c.full_name AS customer FROM orders o JOIN customer c ON c.customer_id = o.customer_id"
    seen = _scripted(app, [_completion("present_report", {"title": "Orders", "sql": sql, "assumptions": []})])
    r = await app.ask(User("alice"), "orders with customer names")
    assert r["kind"] == "report" and len(seen) == 1


@pytest.mark.parametrize("sql, expected", [
    (FAN_OUT, (0, "customer")),
    ("SELECT full_name, customer_id FROM customer JOIN orders USING (customer_id)", (1, "customer")),
    ("SELECT o.amount, order_id FROM customer c JOIN orders o ON o.customer_id = c.customer_id", (1, "orders")),
    ("SELECT customer_id FROM customer", None),                                             # no join
    ("SELECT c.customer_id, o.amount FROM orders o JOIN customer c ON c.customer_id = o.customer_id", None),  # parent id
    ("SELECT c.* FROM customer c JOIN orders o ON o.customer_id = c.customer_id", None),    # star
    ("SELECT c.customer_id, COUNT(*) FROM customer c JOIN orders o ON o.customer_id = c.customer_id "
     "GROUP BY c.customer_id", None),
])
def test_entity_key(app, sql, expected):
    from rebo.agent import entity_key
    assert entity_key(sql, "sqlite", app.catalog.primary_keys) == expected


def _clarify(sqls):
    return _completion("ask_clarifying_question", {"why": "Two readings.", "questions": [
        {"question": "Which customers?", "options": ["paused", "on hold"], "option_sql": sqls}]})


def _gate(app, r):
    return json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])["gate"]


async def test_ask_gate_answers_when_every_reading_gives_the_same_rows(app):
    _scripted(app, [_clarify(["SELECT full_name FROM customer WHERE status = 'paused'",
                              "SELECT full_name FROM customer WHERE status IN ('paused')"])])
    r = await app.ask(User("alice"), "customers on hold")
    assert r["kind"] == "report" and len(r["rows"]) == 10 and _gate(app, r) == "answered"
    assert any("“paused”" in a and "“on hold”" in a for a in r["assumptions"])


@pytest.mark.parametrize("sqls", [
    ["SELECT full_name FROM customer WHERE status = 'paused'", "SELECT full_name FROM customer WHERE status = 'closed'"],
    [],                                                             # no SQL given: cannot check, so ask
    ["SELECT full_name FROM customer WHERE status = 'paused'", "SELECT nope FROM customer"],  # unrunnable: ask
])
async def test_ask_gate_asks_when_readings_differ_or_cannot_be_checked(app, sqls):
    _scripted(app, [_clarify(sqls)])
    r = await app.ask(User("alice"), "customers on hold")
    assert r["kind"] == "clarify" and _gate(app, r) == "asked"


async def test_a_clarification_answer_is_remembered_and_not_asked_again(app):
    from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    def model(messages, info):
        prompt = [p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart)][-1]
        if '"title": "Which customers?"' in prompt:   # the remembered answer is in <learned_knowledge>
            return ModelResponse(parts=[ToolCallPart("present_report", {
                "title": "Paused", "assumptions": [], "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})])
        return ModelResponse(parts=[ToolCallPart("ask_clarifying_question", {"why": "Two readings.", "questions": [
            {"question": "Which customers?", "options": ["paused", "closed"]}]})])

    app.__dict__["agent"] = build_agent(FunctionModel(model))
    alice, bob = User("alice"), User("bob")
    first = await app.ask(alice, "customers on hold")
    assert first["kind"] == "clarify"
    answered = await app.ask(alice, "Which customers? → paused", first["conversation_id"])
    assert answered["kind"] == "report"
    notes = [i for i in app.knowledge.visible(alice, "note") if i["title"] == "Which customers?"]
    assert len(notes) == 1 and notes[0]["body"] == "paused" and notes[0]["source_turn"] == first["turn_id"]
    again = await app.ask(alice, "customers on hold")            # new conversation: not asked twice
    assert again["kind"] == "report"
    assert (await app.ask(bob, "customers on hold"))["kind"] == "clarify"   # personal: bob is still asked


async def test_free_text_that_is_not_an_option_is_not_remembered(app):
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    def model(messages, info):
        return ModelResponse(parts=[ToolCallPart("ask_clarifying_question", {"why": "Two readings.", "questions": [
            {"question": "Which customers?", "options": ["paused", "closed"]}]})])

    app.__dict__["agent"] = build_agent(FunctionModel(model))
    first = await app.ask(User("alice"), "customers on hold")
    await app.ask(User("alice"), "never mind, show me orders", first["conversation_id"])
    assert app.knowledge.visible(User("alice"), "note") == []


async def test_exact_repeat_of_own_confirmed_question_makes_no_model_request(app):
    sql = "SELECT full_name AS customer FROM customer WHERE status = 'paused'"
    seen = _scripted(app, [_completion("present_report", {"title": "Paused", "sql": sql,
                                                          "assumptions": ["Paused is the stored status."]})])
    alice = User("alice")
    first = await app.ask(alice, "Show the paused customers")
    app.feedback(alice, first["turn_id"], "correct")
    calls = len(seen)
    again = await app.ask(alice, "show the paused customers?")
    assert len(seen) == calls and again["kind"] == "report" and again["rows"] == first["rows"]
    assert again["assumptions"] == ["Paused is the stored status."] and again["provenance"]["label"] == "yours"
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (again["turn_id"],))["usage"])
    assert usage["route"] == "direct" and usage["requests"] == 0
    follow = await app.ask(alice, "and the closed ones", again["conversation_id"])   # history stays usable
    assert follow["kind"] == "report" and "route direct" in seen[-1]
    calls = len(seen)
    await app.ask(User("bob"), "show the paused customers")     # someone else's example: the model is asked
    assert len(seen) == calls + 1


async def test_saved_report_with_new_values_is_filled_in_without_the_agent(app):
    sql = "SELECT full_name AS customer FROM customer WHERE status = 'paused'"
    seen = _scripted(app, [_completion("present_report", {"title": "Customers by status", "sql": sql,
                                                          "assumptions": []})])
    fills = []

    def fast(req):
        fills.append(req.content.decode())
        values = ["closed"] if "closed" in fills[-1] else []
        return httpx.Response(200, json=_completion("fill_parameters", {"same_report": bool(values), "values": values}))

    app.__dict__["fast_agent_model"] = build_model(
        "lmstudio:fast", app.settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(fast)))
    alice = User("alice")
    first = await app.ask(alice, "list customers with status paused by name")
    app.feedback(alice, first["turn_id"], "correct")
    calls = len(seen)
    r = await app.ask(alice, "list customers with status closed by name")
    assert len(seen) == calls and len(fills) == 1 and r["kind"] == "report"
    assert "'closed'" in r["sql"] and len(r["rows"]) == 10
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert usage["route"] == "params" and usage["model"] == app.settings.fast_model
    other = await app.ask(alice, "list customers with status and name grouped by month")   # not a value change
    assert len(seen) == calls + 1 and other["kind"] == "report"


async def test_instructions_are_identical_across_turns_and_users(app):
    from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel
    seen = []

    def model(messages, info):
        seen.append((messages[-1].instructions, [p.content for p in messages[-1].parts if isinstance(p, UserPromptPart)]))
        return ModelResponse(parts=[ToolCallPart("reply", {"text": "hi"})])

    app.__dict__["agent"] = build_agent(FunctionModel(model))
    await app.ask(User("alice"), "hello")
    await app.ask(User("bob", role="admin"), "something else")
    (first, p1), (second, p2) = seen
    assert first == second and "customer(40)" in first and "alice" not in first
    assert "Today is" in p1[0] and "'alice'" in p1[0] and "'bob'" in p2[0]


def test_model_profiles_are_applied(app, monkeypatch):
    from pydantic_ai import PromptedOutput

    from rebo import llm
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    gem = build_model("openrouter:google/gemini-3.8-flash", app.settings)
    claude = build_model("openrouter:anthropic/claude-sonnet-5.5", app.settings)
    assert gem.settings["thinking"] == "low" and gem.settings["parallel_tool_calls"] is True
    assert "thinking" not in claude.settings and claude.settings["openrouter_cache_instructions"] is True
    assert claude.settings["openrouter_cache_messages"] is True and "openrouter_cache_messages" not in gem.settings
    base = app.settings.max_tool_calls
    assert app._limits("openrouter:google/gemini-3.8-flash").tool_calls_limit == round(base * 1.6)
    assert app._limits("openrouter:anthropic/claude-sonnet-5.5").tool_calls_limit == base
    monkeypatch.setattr(llm, "PROFILES", [("weak-local", llm.Profile(output="prompted"))])
    assert llm.profile("lmstudio:weak-local-7b").output == "prompted"
    agent = build_agent(build_model("lmstudio:weak-local-7b", app.settings), output="prompted")
    assert isinstance(agent.output_type, PromptedOutput)


async def test_prompted_output_turn_end_to_end(app):
    """A model that answers in JSON text instead of tool calls still produces a validated report."""
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel

    def model(messages, info):
        return ModelResponse(parts=[TextPart(json.dumps({"result": {"kind": "Report", "data": {
            "title": "Paused", "assumptions": [], "sql": "SELECT full_name FROM customer WHERE status = 'paused'"}}}))])

    app.__dict__["agent"] = build_agent(FunctionModel(model), output="prompted")
    r = await app.ask(User("alice"), "paused customers")
    assert r["kind"] == "report" and len(r["rows"]) == 10


@pytest.mark.parametrize("verdict, review", [({"restated": "Names of paused customers.", "ok": True}, "ok"),
                                             ({"ok": False, "concern": "Closed customers may be wanted too."}, "concern")])
async def test_new_report_with_many_assumptions_gets_a_second_opinion(app, verdict, review):
    three = ["Paused is the stored status.", "All regions.", "Any signup date."]
    seen = _scripted(app, [_completion("present_report", {"title": "Paused", "assumptions": three,
                           "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})])
    reviews = []

    def fast(req):
        reviews.append(req.content.decode())
        return httpx.Response(200, json=_completion("review", verdict))

    app.__dict__["fast_agent_model"] = build_model(
        "lmstudio:fast", app.settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(fast)))
    r = await app.ask(User("alice"), "paused customers")
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert len(reviews) == 1 and "first_rows" in reviews[0] and usage["review"] == review and len(seen) == 1
    assert (r["assumptions"][-1] == "Check: Closed customers may be wanted too.") == (review == "concern")
    assert usage["review_restated"] == verdict.get("restated", "")          # back-translation kept for evals
    assert '"restated"' in reviews[0]                                       # and asked for in the review schema


async def test_no_second_opinion_with_two_assumptions_or_fewer(app):
    _scripted(app, [_completion("present_report", {"title": "Paused", "assumptions": ["a", "b"],
                                                   "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})])
    app.__dict__["fast_agent_model"] = build_model("lmstudio:fast", app.settings, http_client=httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: pytest.fail("the reviewer must not be called"))))
    r = await app.ask(User("alice"), "paused customers")
    assert "review" not in json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])


async def test_a_conversation_cannot_be_continued_by_someone_else(app):
    from fastapi.testclient import TestClient

    from rebo.api import create_app
    _scripted(app, [_completion("reply", {"text": "secret plans"})])
    first = await app.ask(User("alice"), "hello")
    with pytest.raises(PermissionError):
        await app.ask(User("bob"), "what did alice ask?", first["conversation_id"])
    client = TestClient(create_app(app, with_ui=False))
    r = client.post("/api/ask", json={"text": "hi", "conversation_id": first["conversation_id"]},
                    headers={"X-User-Id": "bob"})
    assert r.status_code == 403


def test_agui_stream_reports_tool_steps_then_the_result(app):
    from fastapi.testclient import TestClient

    from rebo.api import create_app
    _scripted(app, [_completion("search_values", {"text": "paused"}),
                    _completion("present_report", {"title": "Paused customers", "assumptions": [],
                                                   "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})])
    client = TestClient(create_app(app, with_ui=False))
    body = {"threadId": "conv-1", "runId": "run-1", "state": None, "tools": [], "context": [],
            "forwardedProps": None, "messages": [{"id": "m1", "role": "user", "content": "paused customers"}]}
    with client.stream("POST", "/api/agui", json=body, headers={"X-User-Id": "alice",
                                                                  "Accept": "text/event-stream"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    types = [e["type"] for e in events]
    assert types[0] == "RUN_STARTED" and types[-1] == "RUN_FINISHED"
    assert types.index("STEP_STARTED") < types.index("TEXT_MESSAGE_START")
    assert next(e for e in events if e["type"] == "STEP_STARTED")["stepName"] == "search_values"
    result = next(e for e in events if e.get("name") == "rebo.result")["value"]
    assert result["kind"] == "report" and len(result["rows"]) == 10 and result["conversation_id"] == "conv-1"
    other = client.post("/api/agui", json=body, headers={"X-User-Id": "bob"})
    assert other.status_code == 403


async def test_exact_answer_cache_hits_and_invalidates(app):
    sql = "SELECT full_name AS customer FROM customer WHERE status = 'paused'"
    seen = _scripted(app, [_completion("present_report", {"title": "Paused", "sql": sql,
                                                          "assumptions": ["Paused is the stored status."]})])
    alice = User("alice")
    first = await app.ask(alice, "Who is paused?")
    again = await app.ask(alice, "who is  paused")                         # same question: no model request
    assert len(seen) == 1 and again["rows"] == first["rows"] and again["assumptions"] == first["assumptions"]
    route = lambda r: json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])["route"]
    assert route(again) == "cache"
    await app.ask(User("bob"), "who is paused")                            # another user: not shared
    assert len(seen) == 2
    await app.ask(alice, "who is paused", again["conversation_id"])        # inside a conversation: not cached
    assert len(seen) == 3
    app.knowledge.add(User("ada", role="admin"), kind="note", title="fiscal year", body="starts in April")
    await app.ask(alice, "who is paused")                                  # knowledge changed: asked again
    assert len(seen) == 4
    hit = await app.ask(alice, "who is paused")
    assert len(seen) == 4 and route(hit) == "cache"
    app.settings.model = "lmstudio:other"                                   # another model: not its cache
    await app.ask(alice, "who is paused")
    assert len(seen) == 5
    app.settings.model = "openrouter:anthropic/claude-sonnet-5.5"
    hit = await app.ask(alice, "who is paused")
    assert len(seen) == 5 and route(hit) == "cache"                       # the first model's entry is still there
    app.feedback(alice, hit["turn_id"], "wrong")                           # a wrong answer leaves the cache
    await app.ask(alice, "who is paused")
    assert len(seen) == 6


def test_turn_limits_put_the_cost_cap_in_list_prices(monkeypatch):
    from decimal import Decimal

    from rebo import llm
    sonnet = llm.turn_limits("openrouter:anthropic/claude-sonnet-5.5", tool_calls=25, cost_cap_usd=0.5)
    assert sonnet.cost_limit == Decimal("0.5") and sonnet.tool_calls_limit == 25   # genai-prices agrees here
    haiku = llm.turn_limits("openrouter:anthropic/claude-haiku-5.5", tool_calls=25, cost_cap_usd=0.5)
    theirs, ours = llm.genai_price("openrouter:anthropic/claude-haiku-5.5"), 0.15
    assert haiku.cost_limit == Decimal(str(round(0.5 * theirs / ours, 6)))
    assert llm.turn_limits("lmstudio:local-model", tool_calls=25, cost_cap_usd=0.5).cost_limit is None
    assert llm.turn_limits("openrouter:anthropic/claude-sonnet-5.5", tool_calls=25, cost_cap_usd=0).cost_limit is None
    monkeypatch.setattr(llm, "genai_price", lambda spec, **kw: None)           # not covered: token limits instead
    fallback = llm.turn_limits("openrouter:anthropic/claude-sonnet-5.5", tool_calls=25, cost_cap_usd=0.5)
    assert fallback.cost_limit is None and fallback.input_tokens_limit == 200_000 and fallback.output_tokens_limit == 10_000


async def test_a_turn_over_its_cost_cap_stops_with_the_budget_message(app, monkeypatch):
    from rebo import llm, messages
    monkeypatch.setattr(llm, "genai_price", lambda spec, **kw: None)           # enforce via token limits
    _scripted(app, [_completion("search_values", {"text": "paused"})])        # would keep exploring
    app.settings.cost_per_turn_usd = 0.0001                                    # about 40 input tokens of Sonnet
    r = await app.ask(User("alice"), "paused customers")
    assert r["kind"] == "error" and r["message"] == messages.say("error_budget")


async def test_per_user_rate_limit(app):
    from fastapi.testclient import TestClient

    from rebo.api import create_app
    from rebo.service import RateLimited
    _scripted(app, [_completion("reply", {"text": "hi"})])
    app.settings.per_user_per_minute = 2
    await app.ask(User("alice"), "one")
    await app.ask(User("alice"), "two")
    with pytest.raises(RateLimited):
        await app.ask(User("alice"), "three")
    await app.ask(User("bob"), "one")                                          # per person
    r = TestClient(create_app(app, with_ui=False)).post("/api/ask", json={"text": "four"}, headers={"X-User-Id": "alice"})
    assert r.status_code == 429


def test_profile_output_retries_reach_the_agent(app, monkeypatch):
    from rebo import llm
    assert llm.profile("lmstudio:google/gemma-4-e2b").output_retries == 4
    assert llm.profile("openrouter:anthropic/claude-sonnet-5.5").output_retries == 2
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    app.settings.model = "lmstudio:google/gemma-4-e2b"
    assert app.agent._max_output_retries == 4


async def test_rate_limits_are_waited_out_not_failed(monkeypatch):
    from pydantic_ai.exceptions import ModelHTTPError
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel

    from rebo.llm import PatientModel
    calls = []

    def flaky(messages, info):
        calls.append(1)
        if len(calls) <= 2:
            raise ModelHTTPError(429, "gemini-3.8-flash", body={"error": {"message": "Please retry in 0.01s."}})
        return ModelResponse(parts=[TextPart("ok")])

    from pydantic_ai import Agent
    patient = PatientModel(FunctionModel(flaky), max_wait_s=10)
    patient._delay = lambda e: 0.01                       # keep the test fast; parsing is tested below
    assert (await Agent(patient).run("hi")).output == "ok" and len(calls) == 3

    def always_429(messages, info):
        raise ModelHTTPError(429, "m", body={"error": {"message": "retry in 1s"}})
    with pytest.raises(ModelHTTPError):
        await Agent(PatientModel(FunctionModel(always_429), max_wait_s=0.5)).run("hi")   # budget exhausted

    def server_error(messages, info):
        raise ModelHTTPError(500, "m", body="boom")
    with pytest.raises(ModelHTTPError):
        await Agent(PatientModel(FunctionModel(server_error))).run("hi")             # only 429 is retried

    p = PatientModel(FunctionModel(flaky))
    assert p._delay(ModelHTTPError(429, "m", body={"error": {"message": "Please retry in 47.75s."}})) == 48.75
    assert p._delay(ModelHTTPError(429, "m", body={"details": [{"retryDelay": "12s"}]})) == 13
    assert p._delay(ModelHTTPError(429, "m", body="slow down")) == 30.0


def test_only_remote_models_are_patient(app, monkeypatch):
    from rebo.llm import PatientModel
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    assert isinstance(build_model("google:gemini-3.8-flash", app.settings), PatientModel)
    assert not isinstance(build_model("lmstudio:google/gemma-4-e2b", app.settings), PatientModel)


async def test_each_question_is_one_traced_span_and_the_turn_keeps_its_trace_id(app):
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _scripted(app, [_completion("reply", {"text": "hi"})])
    r = await app.ask(User("alice"), "hello")
    spans = [s for s in exporter.get_finished_spans() if s.name == "rebo.ask"]
    if not spans:  # a tracer provider was already set globally in this process: nothing to assert on
        pytest.skip("global tracer provider already configured")
    assert spans[-1].attributes["rebo.kind"] == "answer" and spans[-1].attributes["rebo.user"] == "alice"
    assert r["trace_id"] == format(spans[-1].context.trace_id, "032x")
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert usage["trace_id"] == r["trace_id"]


C_O = "FROM customer c JOIN orders o ON o.customer_id = c.customer_id"


@pytest.mark.parametrize("sql, trap", [
    ("SELECT full_name FROM customer WHERE email = NULL", "NULL"),
    ("SELECT full_name FROM customer WHERE customer_id NOT IN (SELECT customer_id FROM orders)", "NOT IN"),
    ("SELECT c.full_name, o.amount FROM customer c LEFT JOIN orders o ON o.customer_id = c.customer_id "
     "WHERE o.amount > 10", "LEFT JOIN"),
    (f"SELECT SUM(c.customer_id) {C_O}", "sums"),
    ("SELECT c.full_name, o.amount FROM customer c JOIN orders o", "without a join condition"),
    ("SELECT c.full_name, o.amount FROM customer c, orders o", "without a join condition"),
    # not traps
    ("SELECT full_name FROM customer WHERE email IS NULL", None),
    ("SELECT full_name FROM customer WHERE customer_id NOT IN (1, 2)", None),
    ("SELECT c.full_name FROM customer c LEFT JOIN orders o ON o.customer_id = c.customer_id "
     "WHERE o.order_id IS NULL", None),                                                   # anti-join
    (f"SELECT SUM(o.amount) {C_O}", None),                                               # many side
    (f"SELECT SUM(DISTINCT c.customer_id) {C_O}", None),
    ("SELECT c.full_name FROM customer c CROSS JOIN orders o", None),                    # said on purpose
    ("SELECT c.full_name FROM customer c, orders o WHERE o.customer_id = c.customer_id", None),  # old-style join
])
def test_sql_trap(app, sql, trap):
    from rebo.agent import sql_trap
    found = sql_trap(sql, "sqlite", app.catalog.primary_keys)
    assert (found is None) if trap is None else (trap in found)


async def test_sql_trap_gets_one_retry_before_the_zero_row_retry(app):
    trap = {"title": "Paused", "sql": "SELECT full_name FROM customer WHERE status = 'paused' AND email <> NULL",
            "assumptions": []}
    seen = _scripted(app, [_completion("present_report", trap)])
    r = await app.ask(User("alice"), "paused customers with an email")
    # the trap is named first (it explains the 0 rows); the 0-row retry follows; the third attempt stands
    assert r["kind"] == "report" and len(seen) == 3 and "compares with NULL" in seen[1]


PAUSED = "SELECT full_name FROM customer WHERE status = 'paused'"
THREE = ["Paused is the stored status.", "All regions.", "Any signup date."]


def _fast_by_tool(app, replies: dict[str, dict]):
    """Fast model answering each structured call by its output tool name; returns the tool names called."""
    called = []

    def fast(req):
        name = json.loads(req.content)["tools"][0]["function"]["name"]
        called.append(name)
        return httpx.Response(200, json=_completion(name, replies[name]))

    app.__dict__["fast_agent_model"] = build_model(
        "lmstudio:fast", app.settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(fast)))
    return called


async def test_agreement_check_keeps_the_answer_when_a_candidate_returns_the_same_rows(app):
    app.settings.agreement_check = True
    _scripted(app, [_completion("present_report", {"title": "Paused", "assumptions": list(THREE), "sql": PAUSED})])
    called = _fast_by_tool(app, {"review": {"restated": "Paused customers.", "ok": True},
                                 "write_queries": {"queries": [
                                     {"reading": "Paused customers.",  # same rows, written differently
                                      "sql": "SELECT c.full_name AS name, c.status FROM customer c "
                                             "WHERE c.status IN ('paused')"},
                                     {"reading": "Closed customers.",
                                      "sql": "SELECT full_name FROM customer WHERE status = 'closed'"}]}})
    r = await app.ask(User("alice"), "paused customers")
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert usage["agreement"] == "agreed:1/2" and "judge" not in called
    assert r["assumptions"] == THREE and len(r["rows"]) == 10
    assert usage["agreement_tokens"]["input_tokens"] > 0


@pytest.mark.parametrize("verdict, outcome, note", [
    ({"ambiguous": False, "best": 1}, "candidate",
     "Check: another reading gives a different result: Closed customers. If that is what you meant, say so."),
    ({"ambiguous": True, "readings": ["paused customers", "closed customers"]}, "ambiguous",
     "Check: this can be read two ways. 1) Paused customers. 2) Closed customers. This report uses the first."),
    ({"ambiguous": False, "best": 0}, "report", None)])
async def test_agreement_check_disagreement_goes_to_the_judge_and_never_swaps_the_answer(app, verdict, outcome, note):
    app.settings.agreement_check = True
    _scripted(app, [_completion("present_report", {"title": "Paused", "assumptions": list(THREE), "sql": PAUSED})])
    called = _fast_by_tool(app, {"review": {"restated": "Paused customers.", "ok": True},
                                 "write_queries": {"queries": [
                                     {"reading": "Closed customers",
                                      "sql": "SELECT full_name FROM customer WHERE status = 'closed'"},
                                     {"reading": "Broken.", "sql": "SELECT nope FROM customer"},  # failure ignored
                                     {"reading": "Never run.", "sql": "UPDATE customer SET status = 'x'"}]},
                                 "judge": verdict})
    r = await app.ask(User("alice"), "paused customers")
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert usage["agreement"] == f"disagreed:{outcome}" and called.count("judge") == 1
    assert r["sql"] == PAUSED and len(r["rows"]) == 10  # the report itself is kept
    assert r["assumptions"] == THREE + ([note] if note else [])


async def test_agreement_check_off_by_default_makes_no_extra_calls(app):
    assert app.settings.agreement_check is False
    _scripted(app, [_completion("present_report", {"title": "Paused", "assumptions": list(THREE), "sql": PAUSED})])
    called = _fast_by_tool(app, {"review": {"restated": "Paused customers.", "ok": True}})
    r = await app.ask(User("alice"), "paused customers")
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert called == ["review"] and "agreement" not in usage


async def test_agreement_check_errors_never_block_the_answer(app):
    app.settings.agreement_check = True
    _scripted(app, [_completion("present_report", {"title": "Paused", "assumptions": list(THREE), "sql": PAUSED})])
    _fast_by_tool(app, {"review": {"restated": "Paused customers.", "ok": True}})  # no reply for write_queries
    r = await app.ask(User("alice"), "paused customers")
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert r["kind"] == "report" and usage["agreement"] == "error" and r["assumptions"] == THREE


@pytest.mark.parametrize("on", [True, False])
async def test_shape_check_offers_a_saved_report_with_the_same_query_shape_once(app, on):
    app.settings.shape_check = on
    saved = app.add_knowledge(User("ada", role="admin"), kind="example", title="Paused customers", question="paused customers",
                              sql="SELECT full_name AS customer FROM customer WHERE status = 'paused'")["item"]
    draft = {"title": "On a break", "sql": "SELECT full_name FROM customer WHERE status = 'closed'", "assumptions": []}
    adapted = {**draft, "sql": saved["sql"], "used_knowledge": [saved["id"]]}
    seen = _scripted(app, [_completion("present_report", draft), _completion("present_report", adapted)])
    r = await app.ask(User("alice"), "zzz people taking a break")
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    if on:
        assert len(seen) == 2 and "nearly the same query shape" in seen[1] and saved["id"] in seen[1]
        assert usage["shape"] == "adapted"
    else:
        assert len(seen) == 1 and "shape" not in usage


def test_shape_matches_skip_what_was_shown_and_unlike_queries(app):
    ada = User("ada", role="admin")
    a = app.add_knowledge(ada, kind="example", title="Paused", sql="SELECT full_name FROM customer WHERE status = 'paused'")["item"]
    app.add_knowledge(ada, kind="example", title="Order totals", sql="SELECT state, SUM(amount) FROM orders GROUP BY state")
    near = app.shape_matches(User("bob"), "SELECT full_name FROM customer WHERE status = 'closed'")
    assert [i["id"] for i, _ in near] == [a["id"]] and near[0][1] == 1.0
    assert app.shape_matches(User("bob"), "SELECT full_name FROM customer WHERE status = 'closed'", exclude={a["id"]}) == []


async def test_a_check_that_had_to_step_in_sends_the_turn_to_the_stronger_model(app):
    trap = _completion("present_report", {"title": "Paused", "assumptions": [],
                                          "sql": "SELECT full_name FROM customer WHERE status = 'paused' AND email <> NULL"})
    good = _completion("present_report", {"title": "Paused", "assumptions": [],
                                          "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})
    cheap = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=trap)))
    strong = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=good)))
    app.__dict__["agent"] = build_agent(build_model("lmstudio:cheap", app.settings, http_client=cheap))
    app.__dict__["escalation_model"] = build_model("lmstudio:strong", app.settings, http_client=strong)
    app.settings.escalate_model = "lmstudio:strong"
    r = await app.ask(User("alice"), "paused customers with an email")
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert r["kind"] == "report" and len(r["rows"]) == 10 and "NULL" not in r["sql"]
    assert usage["escalated"] is True and usage["escalated_for"] == "trap" and usage["before"]["model"] != "lmstudio:strong"


async def test_no_escalation_when_no_check_steps_in(app):
    good = _completion("present_report", {"title": "Paused", "assumptions": [],
                                          "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})
    cheap = httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, json=good)))
    app.__dict__["agent"] = build_agent(build_model("lmstudio:cheap", app.settings, http_client=cheap))
    app.__dict__["escalation_model"] = build_model("lmstudio:strong", app.settings, http_client=httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: pytest.fail("the stronger model must not be called"))))
    app.settings.escalate_model = "lmstudio:strong"
    r = await app.ask(User("alice"), "paused customers")
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
    assert r["kind"] == "report" and usage["escalated"] is False


def test_cost_counts_the_discarded_run():
    from rebo.llm import cost
    first = {"model": "anthropic/claude-haiku-5.5", "input_tokens": 1_000_000, "output_tokens": 0}
    both = {"model": "anthropic/claude-sonnet-5.5", "input_tokens": 1_000_000, "output_tokens": 0, "before": first}
    assert cost(both) == round(cost({**both, "before": None}) + cost(first), 5)


async def test_a_join_that_only_multiplies_rows_gets_one_retry(app):
    fanned = {"title": "Customers with orders", "assumptions": [],
              "sql": "SELECT c.full_name FROM customer c JOIN orders o ON o.customer_id = c.customer_id"}
    fixed = {**fanned, "sql": "SELECT c.full_name FROM customer c WHERE EXISTS "
                              "(SELECT 1 FROM orders o WHERE o.customer_id = c.customer_id)"}
    seen = _scripted(app, [_completion("present_report", fanned), _completion("present_report", fixed)])
    r = await app.ask(User("alice"), "customers who ordered")
    assert len(seen) == 2 and "multiplies" in seen[1] and len(r["rows"]) == 40


def test_fanout_probes_skip_used_joins_and_counted_rows():
    from rebo.safety import fanout_probes
    assert fanout_probes("SELECT c.full_name, o.amount FROM customer c JOIN orders o ON o.customer_id = c.customer_id", "sqlite") == []
    assert fanout_probes("SELECT c.full_name, COUNT(*) FROM customer c JOIN orders o ON o.customer_id = c.customer_id "
                         "GROUP BY c.full_name", "sqlite") == []
    [(table, probe)] = fanout_probes("SELECT c.full_name FROM customer c JOIN orders o ON o.customer_id = c.customer_id", "sqlite")
    assert table == "orders" and "EXISTS" in probe
