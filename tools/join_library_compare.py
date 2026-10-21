"""Do confirmed reports' joins make join-path finding right more often? Offline test (B-055).

    uv run python tools/join_library_compare.py <state.db> <gold.jsonl> <dialect> [--out results.json]

For each gold report with joins, leaving it out: the other reports' joins form the confirmed-join
library. For every join of the report (table A to table B), the bot's join_path(A, B) is asked twice,
with today's sources only (declared, inferred, learned items) and with the library added; it is right
when the path is that single join. No LLM, the state file is only read.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from rebo.catalog import Catalog
from rebo.evals import load_cases
from rebo.knowledge import confirmed_join_rows
from rebo.safety import join_edges
from rebo.store import Store


def run(state: Path, path: str, dialect: str) -> dict:
    cat = Catalog(Store(state))
    edges = {c["id"]: join_edges(c["gold_sql"], dialect) for c in load_cases(path) if c.get("gold_sql")}
    base = lib = total = 0
    rows = []
    for cid, mine in edges.items():
        if not mine:
            continue
        others = Counter(e for k, es in edges.items() if k != cid for e in es)
        library = confirmed_join_rows(others)
        for e in mine:
            total += 1
            want = {(e[0], e[1], e[2], e[3])}
            def right(p):
                if p is None or len(p) != 1:
                    return False
                j = p[0]
                l, r = sorted([(j["from_table"].lower(), j["from_cols"].lower()), (j["to_table"].lower(), j["to_cols"].lower())])
                return {(l[0], l[1], r[0], r[1])} == want
            b = right(cat.join_path(e[0], e[2]))
            w = right(cat.join_path(e[0], e[2], library))
            base += b; lib += w
            rows.append({"id": cid, "join": f"{e[0]}.{e[1]} = {e[2]}.{e[3]}", "today": b, "with_library": w})
    return {"run": time.strftime("%Y-%m-%d"), "joins": total, "right_today": f"{base}/{total}",
            "right_with_library": f"{lib}/{total}", "rows": rows}


if __name__ == "__main__":
    a = sys.argv[1:]
    out = a[a.index("--out") + 1] if "--out" in a else None
    res = run(Path(a[0]), a[1], a[2])
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    if out:
        Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
