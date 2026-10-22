"""Score the latest report the bot gave to each question against the gold query, two ways. No model.

    REBO_CONFIG=<config> uv run python tools/rescore.py <cases.jsonl> [--since/--until epoch-seconds] [--out results.json]

strict        evals.columns_match: same rows by content (the eval runner's ExecutionMatch)
same numbers  the same multiset of numbers, ignoring every text value, column order and layout.
              Shows answers that are right but presented differently (a month as "Apr 2025" instead
              of "2025-04", a country name instead of its code, a pivoted table); a wrong filter or
              join still changes the numbers. Identifier columns the bot added (an id, a code) make
              this stricter, not looser, so it is checked with and without the bot's extra columns.
Use it to re-score a run after the gold set is corrected, without asking the model again.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from rebo.evals import columns_match, load_cases
from rebo.service import App
from rebo.settings import get_settings


def numbers(rows: list[list]) -> list[float]:
    return sorted(float(v) for r in rows for v in r if isinstance(v, (int, float)) and not isinstance(v, bool))


def _close(a: float, b: float) -> bool:
    """Equal up to rounding: large amounts to whole units (rupees), small numbers (rates, averages)
    to two decimals, so 0.96 % and 0.97 % still differ."""
    return abs(a - b) <= (0.51 if abs(a) >= 1000 else 0.006) or abs(a - b) <= abs(a) * 1e-6


def same_numbers(gold: list[list], mine: list[list]) -> bool:
    """Either exactly the same numbers in any layout (a pivoted table), or the same number of rows with
    every gold number present (within rounding) and at most two added numbers per row (an id, a count)."""
    g, m = numbers(gold), numbers(mine)
    if not g:
        return False
    if len(g) == len(m) and all(_close(x, y) for x, y in zip(g, m)):
        return True
    if len(mine) != len(gold) or len(m) - len(g) > 2 * len(gold):
        return False
    pool = list(m)
    for x in g:
        hit = next((i for i, y in enumerate(pool) if _close(x, y)), None)
        if hit is None:
            return False
        pool.pop(hit)
    return True


def run(path: str, since: float = 0.0, until: float = 9e18) -> dict:
    app = App(get_settings())
    rows = []
    for c in load_cases(path):
        t = app.store.one("SELECT sql FROM turn WHERE question=? AND kind='report' AND owner LIKE 'eval-%' AND created_at >= ? "
                          "AND created_at < ? ORDER BY created_at DESC LIMIT 1", (c["question"], since, until))
        if not t:
            rows.append({"id": c["id"], "strict": False, "same_numbers": False, "note": "no report"})
            continue
        gold = app._run_report_sql(c["gold_sql"]).rows
        mine = app._run_report_sql(t["sql"]).rows
        rows.append({"id": c["id"], "strict": columns_match(gold, mine), "same_numbers": columns_match(gold, mine) or same_numbers(gold, mine)})
    n = len(rows)
    return {"run": time.strftime("%Y-%m-%d"), "cases": path, "strict": f"{sum(r['strict'] for r in rows)}/{n}",
            "same_numbers": f"{sum(r['same_numbers'] for r in rows)}/{n}", "rows": rows}


if __name__ == "__main__":
    a = sys.argv[1:]
    res = run(a[0], float(a[a.index("--since") + 1]) if "--since" in a else 0.0,
              float(a[a.index("--until") + 1]) if "--until" in a else 9e18)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    print("not matching:", [r["id"] for r in res["rows"] if not r["same_numbers"]])
    if "--out" in a:
        Path(a[a.index("--out") + 1]).write_text(json.dumps(res, indent=1), encoding="utf-8")
