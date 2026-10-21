"""Run an eval set with the current settings and save a results file (per-case outcome, turns'
token usage, escalations, estimated cost). Model choice comes from rebo.yaml / REBO_* env.

    uv run python tools/eval_run.py fixtures/jms_staging/eval.jsonl fixtures/jms_staging/eval_results_<name>.json [limit]
    uv run python tools/eval_run.py fixtures/jms_staging/gold_custom_reports.jsonl <out.json> --use-drafts

--use-drafts asks each case's `draft_question` (agent-written, B-014) and labels the results file as
draft questions, not PO-validated: not an accuracy result.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from rebo.evals import DRAFT_LABEL, cost, load_cases, run_eval
from rebo.service import App


async def main(cases: str, out: str, limit: int = 0, use_drafts: bool = False) -> None:
    app = App()
    started = time.time()
    res = await run_eval(app, cases, limit=limit, use_drafts=use_drafts)
    turns = app.store.all("SELECT question, kind, payload, usage FROM turn WHERE owner='eval' AND created_at >= ?",
                          (started,))
    by_q = {t["question"]: t for t in turns}
    qs = {c["id"]: c["question"] for c in load_cases(cases, use_drafts=use_drafts)}
    for c in res["cases"]:
        t = by_q.get(qs[c["id"]]) or {}
        p = json.loads(t.get("payload") or "{}")
        u = json.loads(t.get("usage") or "{}")
        c.update(question=qs[c["id"]], usage=u, cost_usd=cost(u))
        if c["kind"] == "report":
            c.update(title=p.get("title"), sql=p.get("sql"), assumptions=p.get("assumptions"))
        elif c["kind"] == "clarify":
            c.update(questions=p.get("questions"))
    costs = [c["cost_usd"] for c in res["cases"] if c["cost_usd"] is not None]
    summary = {"reports": sum(c["kind"] == "report" for c in res["cases"]),
               "clarify": sum(c["kind"] == "clarify" for c in res["cases"]),
               "clarify_rate": round(sum(c["kind"] == "clarify" for c in res["cases"]) / max(len(res["cases"]), 1), 3),
               "gate_answered": sum(c["usage"].get("gate") == "answered" for c in res["cases"]),
               "errors": sum(c["kind"] == "error" for c in res["cases"]),
               "escalated": sum(bool(c["usage"].get("escalated")) for c in res["cases"]),
               "median_seconds": sorted(c["seconds"] for c in res["cases"])[len(res["cases"]) // 2],
               "total_cost_usd": round(sum(costs), 4) if costs else None}
    scored = [c["scores"]["ExecutionMatch"] for c in res["cases"] if "ExecutionMatch" in c["scores"]]
    if scored:
        summary["execution_match"] = f"{sum(bool(x) for x in scored)}/{len(scored)}"
    doc = {"run": time.strftime("%Y-%m-%d"), "questions": DRAFT_LABEL if use_drafts else "as in the cases file",
           "model": app.settings.model, "escalate": app.settings.escalate_model,
           "database": app.target.engine.url.render_as_string(hide_password=True), "summary": summary, "cases": res["cases"]}
    Path(out).write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    drafts = "--use-drafts" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--use-drafts"]
    asyncio.run(main(args[0], args[1], int(args[2]) if len(args) > 2 else 0, use_drafts=drafts))
