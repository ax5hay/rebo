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
    ("SELECT c.* FROM customer c JOIN orders o ON o.customer_id = c.customer_id", None),    # star
    ("SELECT c.customer_id, COUNT(*) FROM customer c JOIN orders o ON o.customer_id = c.customer_id "
     "GROUP BY c.customer_id", None),
])
def test_entity_key(app, sql, expected):
    from reportsbot.agent import entity_key
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

    from reportsbot import llm
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    gem = build_model("openrouter:google/gemini-3.8-flash", app.settings)
    claude = build_model("openrouter:anthropic/claude-sonnet-5.5", app.settings)
    assert gem.settings["thinking"] == "low" and gem.settings["parallel_tool_calls"] is True
    assert "thinking" not in claude.settings and claude.settings["openrouter_cache_instructions"] is True
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


@pytest.mark.parametrize("verdict, review", [({"ok": True}, "ok"),
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


async def test_no_second_opinion_with_two_assumptions_or_fewer(app):
    _scripted(app, [_completion("present_report", {"title": "Paused", "assumptions": ["a", "b"],
                                                   "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})])
    app.__dict__["fast_agent_model"] = build_model("lmstudio:fast", app.settings, http_client=httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: pytest.fail("the reviewer must not be called"))))
    r = await app.ask(User("alice"), "paused customers")
    assert "review" not in json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],))["usage"])
