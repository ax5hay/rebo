"""Are the right tables in the first request? Offline comparison of ways to pick the "likely tables" of
the context block (App._context_block). No model.

    REBO_CONFIG=<config> uv run python tools/context_recall.py <cases.jsonl> [--out results.json]

For each question, the gold tables (from `tables`, `hint_tables`, or parsed from `gold_sql`) are
compared with each candidate list:
  top8           today: the first 8 distinct tables of the hybrid schema search
  top12          simply more room
  top8+joined    the first 8, plus tables joined (declared, inferred or learned) to the first 3,
                 in search order, up to 12 in all
A table the first request names saves the agent a search_schema / describe_table round-trip, and every
round-trip re-sends the whole turn.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from rebo.evals import load_cases
from rebo.safety import tables_in
from rebo.service import App
from rebo.settings import get_settings


def candidates(app: App, question: str) -> dict[str, list[str]]:
    hits = app.index.search_schema(question, top=40)
    ranked = list(dict.fromkeys(h["table"] for h in hits))
    return {"top8": ranked[:8], "top12": ranked[:12], "top8+joined": app.likely_tables(question)}  # what ships


def run(path: str) -> dict:
    app = App(get_settings())
    rows = []
    for c in load_cases(path):
        gold = set(c.get("tables") or c.get("hint_tables") or [])
        if not gold and c.get("gold_sql"):
            try:
                gold = set(tables_in(c["gold_sql"], app.target.dialect))
            except Exception:
                continue
        gold &= set(app.catalog.schema)
        if not gold:
            continue
        cand = candidates(app, c["question"])
        rows.append({"id": c["id"], "gold": sorted(gold),
                     **{k: {"recall": round(len(gold & set(v)) / len(gold), 3), "all": gold <= set(v), "n": len(v)} for k, v in cand.items()}})
    summary = {k: {"recall": round(sum(r[k]["recall"] for r in rows) / len(rows), 3),
                   "all_tables": f"{sum(r[k]['all'] for r in rows)}/{len(rows)}",
                   "tables_shown": round(sum(r[k]["n"] for r in rows) / len(rows), 1)} for k in ("top8", "top12", "top8+joined")}
    return {"run": time.strftime("%Y-%m-%d"), "cases": path, "questions": len(rows), "summary": summary, "rows": rows}


if __name__ == "__main__":
    a = sys.argv[1:]
    res = run(a[0])
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    if "--out" in a:
        Path(a[a.index("--out") + 1]).write_text(json.dumps(res, indent=1), encoding="utf-8")
