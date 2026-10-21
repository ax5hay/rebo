"""How many wrong reports does one "Read as" switch fix? Offline check of B-060, no LLM.

    uv run python tools/refine_rescue.py <cases.jsonl> [--since epoch-seconds] [--out results.json]
    (the bot's state and database come from rebo.yaml / REBO_CONFIG)

For each case, the latest report the bot gave to that question (asked by an eval user, after --since)
is compared with the gold query by content (evals.columns_match). For each wrong one, every single
switch a person could make under "Read as" is tried: each value filter set to one stored value, or to
"all except" one value, and kept when its rows match gold.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from rebo.evals import columns_match, load_cases
from rebo.service import App
from rebo.settings import get_settings


def run(path: str, since: float = 0.0) -> dict:
    app = App(get_settings())
    rows = []
    for c in load_cases(path):
        if not c.get("gold_sql"):
            continue
        t = app.store.one("SELECT sql FROM turn WHERE question=? AND kind='report' AND owner LIKE 'eval-%' "
                          "AND created_at >= ? ORDER BY created_at DESC LIMIT 1", (c["question"], since))
        if not t:
            continue
        try:
            gold = app._run_report_sql(c["gold_sql"]).rows
            mine = app._run_report_sql(t["sql"]).rows
        except Exception:
            continue
        if columns_match(gold, mine):
            rows.append({"id": c["id"], "right": True})
            continue
        fix = None
        for f in app.filter_choices(t["sql"]):
            for o in f["options"]:
                for negated in (False, True):
                    try:
                        from rebo.safety import refine_sql
                        res = app._run_report_sql(refine_sql(t["sql"], app.target.dialect, f["index"], [o["value"]], negated))
                    except Exception:
                        continue
                    if columns_match(gold, res.rows):
                        fix = f"{f['column']} {'not ' if negated else ''}{o['value']}"
                        break
                if fix:
                    break
            if fix:
                break
        rows.append({"id": c["id"], "right": False, "one_switch_fix": fix})
    wrong = [r for r in rows if not r["right"]]
    return {"run": time.strftime("%Y-%m-%d"), "cases": path, "reports": len(rows), "wrong": len(wrong),
            "fixed_by_one_switch": sum(bool(r["one_switch_fix"]) for r in wrong), "rows": rows}


if __name__ == "__main__":
    a = sys.argv[1:]
    since = float(a[a.index("--since") + 1]) if "--since" in a else 0.0
    out = a[a.index("--out") + 1] if "--out" in a else None
    res = run(a[0], since)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1), json.dumps(res["rows"]))
    if out:
        Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
