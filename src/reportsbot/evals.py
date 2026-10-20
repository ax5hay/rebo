"""Evaluation with pydantic-evals. Input: JSONL, one case per line:

  {"id": "...", "question": "...", "gold_sql": "... optional ...",
   "min_rows": 1, "max_rows": null, "tables": ["optional", "expected", "tables"]}

Scores per case: produced a report, SQL ran, rows within range, expected tables used, and
(when gold_sql is given) execution match = same multiset of rows, ignoring column order and
names. Confirmed reports can be exported as gold cases, so the eval set grows with use.
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


def _rows_key(columns: list[str], rows: list[list[Any]]) -> Counter:
    return Counter(tuple(sorted(map(str, r))) for r in rows)


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
        return _rows_key(ref.columns, ref.rows) == _rows_key(ctx.output["columns"], ctx.output["rows"])


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
