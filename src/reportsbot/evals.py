"""Evaluation with pydantic-evals. Input: JSONL, one case per line:

  {"id": "...", "question": "...", "gold_sql": "... optional ...",
   "min_rows": 1, "max_rows": null, "tables": ["optional", "expected", "tables"]}

Scores per case: produced a report, SQL ran, rows within range, expected tables used, and
(when gold_sql is given) execution match = Spider 2.0-style column match (see columns_match). Confirmed reports can be exported as gold cases, so the eval set grows with use.
See docs/10-evals-and-observability.md.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from .knowledge import User
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


async def run_eval(app: App, path: str, *, limit: int = 0, user: str = "eval") -> dict[str, Any]:
    lines = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    if limit:
        lines = lines[:limit]
    cases = [Case(name=c["id"], inputs=c["question"], expected_output=c.get("gold_sql"),
                  metadata={k: c.get(k) for k in ("min_rows", "max_rows", "tables")}) for c in lines]
    ds = Dataset(name=Path(path).stem, cases=cases, evaluators=[IsReport(), RowsInRange(), UsesTables(app.target.dialect),
                                          ExecutionMatch(app)])
    evaluator = User(id=user)

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


def export_confirmed(app: App, path: str) -> int:
    """Write every verified example as an eval case with its SQL as gold."""
    rows = app.store.all("SELECT id, question, sql FROM knowledge WHERE kind='example' AND status='verified'")
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"id": r["id"], "question": r["question"], "gold_sql": r["sql"], "min_rows": 0}) + "\n")
    return len(rows)
