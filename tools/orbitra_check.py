"""Offline checks of ReBo on the Orbitra company database. No model is called anywhere.

    REBO_CONFIG=fixtures/orbitra/rebo.yaml uv run python tools/orbitra_check.py [--out results.json]

1. Gold queries: every reference query passes ReBo's guard (read-only, no protected columns, known
   tables) and returns at least min_rows rows on the database.
2. Retrieval: for each question, are the gold tables among the 8 "likely tables" the first request
   shows the model (App._context_block)? recall@8 per question, and the misses.
3. $0 answers: in a throwaway copy of the bot's memory, an admin saves each gold report as verified
   knowledge; asking the same question again must return the gold rows through a route with no model
   call (the agent is replaced by one that fails if called).
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from rebo.evals import columns_match, load_cases
from rebo.knowledge import User
from rebo.safety import guard
from rebo.service import App
from rebo.settings import get_settings

GOLD = "fixtures/orbitra/gold.jsonl"


def check_gold(app: App, cases: list[dict]) -> list[dict]:
    out = []
    for c in cases:
        t0 = time.perf_counter()
        try:
            g = guard(c["gold_sql"], dialect=app.target.dialect, schema=app.catalog.schema, sensitive=app.catalog.sensitive,
                      allowed_tables=app.allowed_tables, row_cap=app.settings.row_limit + 1)
            res = app.target.run(g.sql, max_rows=app.settings.row_limit)
            out.append({"id": c["id"], "ok": len(res.rows) >= c.get("min_rows", 1), "rows": len(res.rows), "truncated": res.truncated,
                        "ms": int((time.perf_counter() - t0) * 1000)})
        except Exception as e:
            out.append({"id": c["id"], "ok": False, "error": str(e)[:300]})
    return out


def check_retrieval(app: App, cases: list[dict]) -> list[dict]:
    out = []
    for c in cases:
        hits = app.index.search_schema(c["question"], top=20)
        likely = list(dict.fromkeys(h["table"] for h in hits))[:8]
        gold = set(c["tables"])
        found = gold & set(likely)
        out.append({"id": c["id"], "recall": round(len(found) / len(gold), 2), "missing": sorted(gold - found), "likely": likely})
    return out


async def check_free_routes(settings, cases: list[dict]) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        state = Path(tmp) / "state"
        shutil.copytree(settings.state_dir, state)
        app = App(settings.model_copy(update={"state_dir": state, "state_url": ""}))

        class NoModel:  # any model call fails the check
            def __getattr__(self, name):
                raise AssertionError("a model was called")
        app.__dict__.update(agent=NoModel(), fast_agent_model=NoModel(), escalation_model=None, decide_model=None)
        admin = User("orbitra-admin", role="admin")
        out = []
        for c in cases:
            try:
                app.add_knowledge(admin, kind="example", title=c["question"][:80], question=c["question"], sql=c["gold_sql"])
                r = await app.ask(User("orbitra-admin", role="admin"), c["question"])
                gold = app._run_report_sql(c["gold_sql"]).rows
                out.append({"id": c["id"], "kind": r["kind"], "route": r.get("route"), "match": r["kind"] == "report" and columns_match(gold, r["rows"])})
            except Exception as e:
                out.append({"id": c["id"], "kind": "error", "error": f"{type(e).__name__}: {str(e)[:200]}"})
        return out


def main() -> None:
    a = sys.argv[1:]
    out_path = a[a.index("--out") + 1] if "--out" in a else None
    settings = get_settings()
    app = App(settings)
    cases = load_cases(GOLD)
    gold = check_gold(app, cases)
    retrieval = check_retrieval(app, cases)
    free = asyncio.run(check_free_routes(settings, cases))
    summary = {
        "run": time.strftime("%Y-%m-%d"), "cases": len(cases),
        "tables_in_db": len(app.catalog.schema), "protected_columns": sorted(f"{t}.{c}" for t, c in app.catalog.sensitive),
        "gold_queries_ok": f"{sum(g['ok'] for g in gold)}/{len(gold)}",
        "gold_query_ms_max": max((g.get("ms", 0) for g in gold), default=0),
        "retrieval_recall_at_8_mean": round(sum(r["recall"] for r in retrieval) / len(retrieval), 3),
        "retrieval_all_tables_found": f"{sum(r['recall'] == 1 for r in retrieval)}/{len(retrieval)}",
        "free_route_matches": f"{sum(bool(f.get('match')) for f in free)}/{len(free)}",
        "free_routes": sorted({str(f.get("route")) for f in free}),
    }
    print(json.dumps(summary, indent=1))
    bad = [g for g in gold if not g["ok"]] + [f for f in free if not f.get("match")]
    for b in bad[:20]:
        print("FAIL", json.dumps(b)[:300])
    if out_path:
        Path(out_path).write_text(json.dumps({**summary, "gold": gold, "retrieval": retrieval, "free": free}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
