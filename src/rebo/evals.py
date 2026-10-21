"""Evaluation with pydantic-evals. Input: JSONL, one case per line:

  {"id": "...", "question": "...", "gold_sql": "... optional ...",
   "min_rows": 1, "max_rows": null, "tables": ["optional", "expected", "tables"]}

Scores per case: produced a report, SQL ran, rows within range, expected tables used, and
(when gold_sql is given) execution match = Spider 2.0-style column match (see columns_match). Confirmed reports can be exported as gold cases, so the eval set grows with use.
See docs/10-evals-and-observability.md.
"""
from __future__ import annotations

import json
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from .knowledge import User
from .llm import cost  # noqa: F401  (re-exported for tools/eval_run.py)
from .safety import guard, tables_in
from .service import App


def _norm(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).lstrip("-").isdigit()):
        try:
            return f"{float(v):.1f}"
        except ValueError:
            pass
    return str(v).strip()


def columns_match(gold_rows: list[list[Any]], pred_rows: list[list[Any]],
                  gold_columns: list[str] | None = None) -> bool:
    """Judge the answer's content, not its presentation (Spider 2.0-style, with stated tolerances):
      * same number of rows;
      * every gold column's values (as an order-free multiset) appear as some predicted column;
      * extra predicted columns are fine (a report that adds readable columns is not wrong);
      * two adjacent gold text columns may match one predicted column holding them joined by a space
        (first + last name shown as one "Name" column);
      * gold columns named *_id / id are optional (people want names, not surrogate keys);
      * numbers compare at one-decimal precision (a rounded average is the same answer)."""
    if len(gold_rows) != len(pred_rows):
        return False
    if not gold_rows:
        return True
    names = gold_columns or [""] * len(gold_rows[0])
    pred_cols = [Counter(_norm(r[i]) for r in pred_rows) for i in range(len(pred_rows[0]))] if pred_rows[0] else []
    used: set[int] = set()

    def find(want: Counter) -> int | None:
        return next((pi for pi, c in enumerate(pred_cols) if pi not in used and c == want), None)

    gi, width = 0, len(gold_rows[0])
    while gi < width:
        if gi + 1 < width:  # joined form first: a coincidental joined match is far less likely than a single one
            joined = Counter(" ".join(x for x in (_norm(r[gi]), _norm(r[gi + 1])) if x) for r in gold_rows)
            if (hit := find(joined)) is not None:
                used.add(hit)
                gi += 2
                continue
        hit = find(Counter(_norm(r[gi]) for r in gold_rows))
        if hit is None:
            name = names[gi].lower()
            if name == "id" or name.endswith("_id"):
                gi += 1
                continue
            return False
        used.add(hit)
        gi += 1
    return True


@dataclass
class IsReport(Evaluator):
    def evaluate(self, ctx: EvaluatorContext) -> bool:
        return ctx.output.get("kind") == "report"


@dataclass
class RowsInRange(Evaluator):
    def evaluate(self, ctx: EvaluatorContext) -> bool | dict:
        if ctx.output.get("kind") != "report":
            return False
        n = len(ctx.output["rows"])
        lo, hi = ctx.metadata.get("min_rows"), ctx.metadata.get("max_rows")
        return (lo is None or n >= lo) and (hi is None or n <= hi)


@dataclass
class UsesTables(Evaluator):
    dialect: str = "mysql"

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        want = set(ctx.metadata.get("tables") or [])
        if not want or ctx.output.get("kind") != "report":
            return ctx.output.get("kind") == "report"
        return want <= set(tables_in(ctx.output["sql"], self.dialect))


@dataclass
class ExecutionMatch(Evaluator):
    app: Any = None

    def evaluate(self, ctx: EvaluatorContext) -> bool | dict:
        gold = ctx.expected_output
        if not gold or ctx.output.get("kind") != "report":
            return {} if not gold else False
        a = self.app
        g = guard(gold, dialect=a.target.dialect, schema=a.catalog.schema, sensitive=set(), row_cap=a.settings.row_limit + 1)
        ref = a.target.run(g.sql, max_rows=a.settings.row_limit)
        if not ref.rows or ref.truncated:
            return {}  # an empty or truncated gold result proves nothing: not scored
        return columns_match(ref.rows, ctx.output["rows"], ref.columns)


DRAFT_LABEL = "draft questions (agent-written, not PO-validated)"


def load_cases(path: str, *, use_drafts: bool = False) -> list[dict[str, Any]]:
    """Eval cases from JSONL. use_drafts: only rows with a `draft_question`, asked with it instead of
    `question` (B-014). Results from drafts are not accuracy results until a PO validates them."""
    lines = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    if use_drafts:
        lines = [{**c, "question": c["draft_question"]} for c in lines if c.get("draft_question")]
    return lines


def fresh_eval_user() -> str:
    """A new asker per run: the exact answer cache, saved reports and personal knowledge are per person,
    so a fixed eval user would let a second run (or the other arm of an A/B) replay the first run's
    answers at no cost and measure nothing."""
    return f"eval-{uuid.uuid4().hex[:8]}"


async def run_eval(app: App, path: str, *, limit: int = 0, user: str | None = None,
                   use_drafts: bool = False) -> dict[str, Any]:
    lines = load_cases(path, use_drafts=use_drafts)
    if limit:
        lines = lines[:limit]
    cases = [Case(name=c["id"], inputs=c["question"], expected_output=c.get("gold_sql"),
                  metadata={k: c.get(k) for k in ("min_rows", "max_rows", "tables")}) for c in lines]
    ds = Dataset(name=Path(path).stem, cases=cases, evaluators=[IsReport(), RowsInRange(), UsesTables(app.target.dialect),
                                          ExecutionMatch(app)])
    evaluator = User(id=user or fresh_eval_user())

    async def task(question: str) -> dict[str, Any]:
        return await app.ask(evaluator, question)

    report = await ds.evaluate(task, max_concurrency=2)
    report.print(include_input=True, include_output=False)
    out = []
    for c in report.cases:
        out.append({"id": c.name, "kind": c.output.get("kind"), "rows": len(c.output.get("rows") or []),
                    "scores": {k: v.value for k, v in c.assertions.items()},
                    "seconds": round(c.task_duration, 1)})
    return {"cases": out, "failures": [f.name for f in report.failures]}


def _step_text(step: dict[str, Any], prev: dict[str, Any] | None) -> str | None:
    """What the scripted user sends: typed text, an option of the last clarification (as the UI sends
    it), or a follow-up chip of the last report. None when the step does not fit the last turn."""
    if "say" in step:
        return step["say"]
    if "pick" in step and prev and prev["kind"] == "clarify":
        qs = prev["questions"]
        picks = step["pick"] if isinstance(step["pick"], list) else [step["pick"]] * len(qs)
        if len(picks) != len(qs) or any(i >= len(q["options"]) for i, q in zip(picks, qs)):
            return None
        if len(qs) == 1:
            return qs[0]["options"][picks[0]]
        return "; ".join(f"{q['question']} → {q['options'][i]}" for i, q in zip(picks, qs))
    if "follow_up" in step and prev and prev["kind"] == "report" and step["follow_up"] < len(prev.get("follow_ups") or []):
        return prev["follow_ups"][step["follow_up"]]
    return None


async def run_conversations(app: App, path: str, *, limit: int = 0, user: str | None = None) -> dict[str, Any]:
    """Multi-turn eval. JSONL, one conversation per line:

      {"id": "...", "gold_sql": "the report the person is after",
       "turns": [{"say": "..."}, {"pick": 0}, {"follow_up": 1}, {"say": "..."}]}

    `pick` chooses option i of every clarifying question (or a list, one index per question);
    `follow_up` clicks chip i under the last report. A conversation stops at the first report whose
    rows match gold_sql (columns_match). Reports turns to the first correct report, the clarify rate
    and cost per conversation."""
    convs = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    convs = convs[:limit] if limit else convs
    who = User(id=user or fresh_eval_user())
    out = []
    for c in convs:
        g = guard(c["gold_sql"], dialect=app.target.dialect, schema=app.catalog.schema, sensitive=set(),
                  row_cap=app.settings.row_limit + 1)
        ref = app.target.run(g.sql, max_rows=app.settings.row_limit)
        conv_id, prev, turns, solved_at = None, None, [], None
        for step in c["turns"]:
            text = _step_text(step, prev)
            if text is None:
                turns.append({"step": step, "skipped": "does not fit the previous turn"})
                continue
            r = await app.ask(who, text, conv_id)
            conv_id, prev = r["conversation_id"], r
            usage = json.loads((app.store.one("SELECT usage FROM turn WHERE id=?", (r["turn_id"],)) or {}).get("usage")
                               or "{}")
            correct = r["kind"] == "report" and columns_match(ref.rows, r["rows"], ref.columns)
            turns.append({"step": step, "text": text, "kind": r["kind"], "rows": len(r.get("rows") or []),
                          "correct": correct, "route": usage.get("route"), "cost_usd": cost(usage)})
            if correct:
                solved_at = sum("text" in t for t in turns)
                break
        asked = [t for t in turns if "text" in t]
        costs = [t["cost_usd"] for t in asked if t["cost_usd"] is not None]
        out.append({"id": c["id"], "turns_to_first_correct": solved_at, "asked": len(asked),
                    "clarify": sum(t["kind"] == "clarify" for t in asked),
                    "cost_usd": round(sum(costs), 5) if costs else None, "turns": turns})
    solved = [c["turns_to_first_correct"] for c in out if c["turns_to_first_correct"]]
    asked = sum(c["asked"] for c in out)
    costs = [c["cost_usd"] for c in out if c["cost_usd"] is not None]
    summary = {"conversations": len(out), "solved": len(solved),
               "mean_turns_to_first_correct": round(sum(solved) / len(solved), 2) if solved else None,
               "clarify_rate": round(sum(c["clarify"] for c in out) / asked, 3) if asked else None,
               "total_cost_usd": round(sum(costs), 4) if costs else None}
    return {"summary": summary, "conversations": out}


def record_run(app: App, *, kind: str, cases: str, model: str | None, summary: dict, results_file: str | None,
               at: float | None = None) -> str:
    """Keep an eval run's summary in the state store, so Insights can show accuracy over time."""
    import time
    from .store import new_id
    rid = new_id("ev")
    with app.store.tx() as db:
        db.execute("INSERT INTO eval_run(id, at, kind, cases, model, summary, results_file) VALUES(?,?,?,?,?,?,?)",
                   (rid, at or time.time(), kind, cases, model, json.dumps(summary), results_file))
    return rid


def export_confirmed(app: App, path: str) -> int:
    """Write every verified example as an eval case with its SQL as gold."""
    rows = app.store.all("SELECT id, question, sql FROM knowledge WHERE kind='example' AND status='verified'")
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"id": r["id"], "question": r["question"], "gold_sql": r["sql"], "min_rows": 0}) + "\n")
    return len(rows)


async def run_regression(app: App, *, limit: int = 0) -> dict[str, Any]:
    """Replay every shared confirmed report as a test (B-059): its question is asked again, as a new
    person, and the answer's rows are compared by content with what its saved query returns today. The
    run is recorded (kind "regression") so Insights shows it over time. Run it nightly, e.g. from cron:
    `rebo eval --confirmed`. Costs one agent turn per report."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = f"{tmp}/confirmed.jsonl"
        n = export_confirmed(app, path)
        if not n:
            return {"cases": [], "summary": {"reports": 0, "execution_match": "0/0"}, "note": "no shared confirmed reports yet"}
        res = await run_eval(app, path, limit=limit)
    scored = [c["scores"]["ExecutionMatch"] for c in res["cases"] if "ExecutionMatch" in c["scores"]]
    summary = {"reports": sum(c["kind"] == "report" for c in res["cases"]), "errors": sum(c["kind"] == "error" for c in res["cases"]),
               "execution_match": f"{sum(bool(x) for x in scored)}/{len(scored)}"}
    record_run(app, kind="regression", cases="confirmed reports", model=app.settings.model, summary=summary, results_file=None)
    return {**res, "summary": summary}
