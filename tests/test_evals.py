from reportsbot.evals import columns_match


def test_extra_readable_columns_are_allowed_but_values_must_match():
    gold = [[1, "a"], [2, "b"]]
    assert columns_match(gold, [["a", 1, "Oak Court"], ["b", 2, "Elm"]])
    assert not columns_match(gold, [["a", 1], ["c", 2]])
    assert not columns_match(gold, [["a", 1]])                         # row count differs
    assert not columns_match([[1, 1]], [[1, 2]])                         # a predicted column is used once


def test_presentation_tolerances():
    assert columns_match([[11.046]], [[65, 11.0]])                       # rounded average
    assert columns_match([["Ava", "Kim", 9]], [["Ava Kim", 9]], ["first_name", "last_name", "n"])  # joined name
    assert columns_match([[7, "Oak"]], [["Oak"]], ["unit_id", "building"])  # surrogate key optional
    assert not columns_match([[7, "Oak"]], [["Oak"]], ["units", "building"])  # a real value is not optional
    assert columns_match([[None, None]], [[None]], ["first_name", "last_name"])  # empty name both sides


async def test_conversation_eval_counts_turns_to_the_first_correct_report(app, tmp_path):
    import json

    from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    from reportsbot.agent import build_agent
    from reportsbot.evals import run_conversations

    def model(messages, info):
        prompt = [p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart)][-1]
        if "<request>paused</request>" in prompt:
            return ModelResponse(parts=[ToolCallPart("present_report", {
                "title": "Paused", "assumptions": [], "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})])
        if "<request>everyone</request>" in prompt:
            return ModelResponse(parts=[ToolCallPart("present_report", {
                "title": "All", "assumptions": [], "follow_ups": ["paused"], "sql": "SELECT full_name FROM customer"})])
        return ModelResponse(parts=[ToolCallPart("ask_clarifying_question", {"why": "Two readings.", "questions": [
            {"question": "Which customers?", "options": ["closed", "paused"]}]})])

    app.__dict__["agent"] = build_agent(FunctionModel(model))
    gold = "SELECT full_name FROM customer WHERE status = 'paused'"
    path = tmp_path / "conversations.jsonl"
    path.write_text("\n".join(json.dumps(c) for c in [
        {"id": "pick", "gold_sql": gold, "turns": [{"say": "customers on hold"}, {"pick": 1}, {"say": "unused"}]},
        {"id": "chip", "gold_sql": gold, "turns": [{"say": "everyone"}, {"follow_up": 0}]},
        {"id": "never", "gold_sql": gold, "turns": [{"say": "everyone"}, {"pick": 0}]},   # pick after a report: skipped
    ]), encoding="utf-8")
    res = await run_conversations(app, str(path))
    by = {c["id"]: c for c in res["conversations"]}
    assert [by[i]["turns_to_first_correct"] for i in ("pick", "chip", "never")] == [2, 2, None]
    assert by["pick"]["clarify"] == 1 and by["pick"]["asked"] == 2           # stops at the first correct report
    assert by["never"]["turns"][1]["skipped"]
    summary = {k: v for k, v in res["summary"].items() if k != "total_cost_usd"}  # priced from the default model name
    assert summary == {"conversations": 3, "solved": 2, "mean_turns_to_first_correct": 2.0, "clarify_rate": 0.2}


def test_use_drafts_asks_only_drafted_cases_with_the_draft(tmp_path):
    import json

    from reportsbot.evals import load_cases
    path = tmp_path / "gold.jsonl"
    path.write_text("\n".join(json.dumps(c) for c in [
        {"id": "a", "question": "Show me A.", "draft_question": "Which a's are open?", "gold_sql": "SELECT 1"},
        {"id": "b", "question": "Real question?", "gold_sql": "SELECT 1"}]), encoding="utf-8")
    assert [c["question"] for c in load_cases(str(path))] == ["Show me A.", "Real question?"]
    assert [(c["id"], c["question"]) for c in load_cases(str(path), use_drafts=True)] == [("a", "Which a's are open?")]
