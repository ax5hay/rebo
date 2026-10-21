"""Run an eval set with the current settings and save a results file (per-case outcome, turns'
token usage, escalations, estimated cost). Model choice comes from reportsbot.yaml / REPORTSBOT_* env.

    uv run python tools/eval_run.py fixtures/jms_staging/eval.jsonl fixtures/jms_staging/eval_results_<name>.json
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from reportsbot.evals import run_eval
from reportsbot.service import App

# USD per 1M tokens (input, cache read, output), OpenRouter list prices checked 2026-10-21 (docs/20).
PRICES = {
    "anthropic/claude-haiku-5.5": (0.10, 0.01, 0.50),
    "anthropic/claude-sonnet-5.5": (2.00, 0.10, 10.00),
    "google/gemini-3.8-flash": (0.825, 0.0825, 4.125),
    "google/gemini-3.5-flash-lite": (0.30, 0.03, 2.50),
}


def cost(usage: dict) -> float | None:
    name = (usage.get("model") or "").split(":", 1)[-1]
    if name not in PRICES:
        return None
    pin, pcache, pout = PRICES[name]
    cached = usage.get("cache_read_tokens") or 0
    fresh = max((usage.get("input_tokens") or 0) - cached, 0)
    return round((fresh * pin + cached * pcache + (usage.get("output_tokens") or 0) * pout) / 1e6, 5)


async def main(cases: str, out: str) -> None:
    app = App()
    started = time.time()
    res = await run_eval(app, cases)
    turns = app.store.all("SELECT question, kind, payload, usage FROM turn WHERE owner='eval' AND created_at >= ?",
                          (started,))
    by_q = {t["question"]: t for t in turns}
    qs = {json.loads(l)["id"]: json.loads(l)["question"] for l in Path(cases).read_text(encoding="utf-8").splitlines() if l.strip()}
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
               "errors": sum(c["kind"] == "error" for c in res["cases"]),
               "escalated": sum(bool(c["usage"].get("escalated")) for c in res["cases"]),
               "median_seconds": sorted(c["seconds"] for c in res["cases"])[len(res["cases"]) // 2],
               "total_cost_usd": round(sum(costs), 4) if costs else None}
    scored = [c["scores"]["ExecutionMatch"] for c in res["cases"] if "ExecutionMatch" in c["scores"]]
    if scored:
        summary["execution_match"] = f"{sum(bool(x) for x in scored)}/{len(scored)}"
    doc = {"run": time.strftime("%Y-%m-%d"), "model": app.settings.model, "escalate": app.settings.escalate_model,
           "database": "local synthetic copy of JMS staging (seed 7, cap 3000)", "summary": summary, "cases": res["cases"]}
    Path(out).write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
