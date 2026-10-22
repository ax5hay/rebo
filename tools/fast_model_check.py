"""How well does a model do the light model's two recurring jobs? Measured on a gold set.

    REBO_CONFIG=<config> uv run python tools/fast_model_check.py <cases.jsonl> <model spec> [--out results.json]

1. Second opinion (App.review_agent): each correct gold report, and a wrong twin of it (one stored value
   switched to another, or one WHERE condition dropped, so its rows change). A good reviewer flags the
   wrong twins (catch rate) and leaves the correct reports alone (false alarm rate).
2. Filling values (App.param_agent): a gold question that names a stored value ("Karnataka") is asked
   again with another stored value ("Tamil Nadu"); the model must answer "same report" with the new
   value, filled into the saved query (rows compared with the gold query switched the same way).
Uses the model; costs cents for small models.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from pathlib import Path

import sqlglot
from sqlglot import exp

from rebo.evals import columns_match, load_cases
from rebo.llm import build_model, cost
from rebo.safety import fill_params, parameterize, refine_sql
from rebo.service import App
from rebo.settings import get_settings


def wrong_twin(app: App, sql: str) -> str | None:
    fs = app.filter_choices(sql)
    for f in fs:
        other = next((o["value"] for o in f["options"] if o["value"] not in f["values"]), None)
        if other:
            return refine_sql(sql, app.target.dialect, f["index"], [other], f["negated"])
    tree = sqlglot.parse_one(sql, read=app.target.dialect)
    where = tree.args.get("where")
    if where is None:
        return None
    conds = list(where.this.flatten()) if isinstance(where.this, exp.And) else [where.this]
    if len(conds) < 2:
        return None
    kept = conds[1:]
    tree.set("where", exp.Where(this=exp.and_(*kept)))
    return tree.sql(dialect=app.target.dialect)


async def review(app: App, model, question: str, sql: str, usage: list) -> bool:
    res = app._run_report_sql(sql)
    prompt = json.dumps({"question": question, "sql": sql, "assumptions": [], "columns": res.columns,
                         "first_rows": res.rows[:10], "row_count": len(res.rows)}, default=str)
    r = await app.review_agent.run(prompt, model=model)
    usage.append(r.usage)
    return not r.output.ok and bool(r.output.concern.strip())   # True = flagged


async def fill(app: App, model, case: dict, usage: list) -> dict | None:
    sql = case["gold_sql"]
    for f in app.filter_choices(sql):
        for v in f["values"]:
            if not re.search(rf"\b{re.escape(str(v))}\b", case["question"], re.I):
                continue
            other = next((o["value"] for o in f["options"] if o["value"] not in f["values"] and o["count"] > 0), None)
            p = parameterize(sql, app.target.dialect)
            if not other or not p:
                continue
            new_q = re.sub(rf"\b{re.escape(str(v))}\b", str(other), case["question"], flags=re.I)
            expected = app._run_report_sql(refine_sql(sql, app.target.dialect, f["index"], [other], f["negated"])).rows
            prompt = json.dumps({"saved_question": case["question"], "sql_template": p[0], "saved_values": p[1], "new_request": new_q})
            try:
                r = await app.param_agent.run(prompt, model=model)
                usage.append(r.usage)
                out = r.output
                ok = out.same_report and len(out.values) == len(p[1]) and columns_match(
                    expected, app._run_report_sql(fill_params(p[0], app.target.dialect, out.values)).rows)
            except Exception as e:
                ok, out = False, str(e)[:100]
            return {"id": case["id"], "from": v, "to": other, "ok": bool(ok)}
    return None


async def main_async(path: str, spec: str) -> dict:
    app = App(get_settings())
    model = build_model(spec, app.settings)
    usage: list = []
    rows, fills = [], []
    for c in load_cases(path):
        twin = wrong_twin(app, c["gold_sql"])
        if twin is None:
            continue
        try:
            if columns_match(app._run_report_sql(c["gold_sql"]).rows, app._run_report_sql(twin).rows):
                continue   # the twin happens to give the same rows: not wrong
            rows.append({"id": c["id"], "flags_correct": await review(app, model, c["question"], c["gold_sql"], usage),
                         "flags_wrong": await review(app, model, c["question"], twin, usage)})
        except Exception as e:
            rows.append({"id": c["id"], "error": str(e)[:200]})
        f = await fill(app, model, c, usage)
        if f:
            fills.append(f)
    ok_rows = [r for r in rows if "error" not in r]
    total = sum(cost({"model": spec, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                      "cache_read_tokens": getattr(u, "cache_read_tokens", 0)}) or 0 for u in usage)
    return {"run": time.strftime("%Y-%m-%d"), "model": spec, "cases": path,
            "review_pairs": len(ok_rows), "review_errors": len(rows) - len(ok_rows),
            "wrong_caught": f"{sum(r['flags_wrong'] for r in ok_rows)}/{len(ok_rows)}",
            "false_alarms": f"{sum(r['flags_correct'] for r in ok_rows)}/{len(ok_rows)}",
            "fills_right": f"{sum(f['ok'] for f in fills)}/{len(fills)}",
            "cost_usd": round(total, 4), "review": rows, "fills": fills}


if __name__ == "__main__":
    a = sys.argv[1:]
    res = asyncio.run(main_async(a[0], a[1]))
    print(json.dumps({k: v for k, v in res.items() if k not in ("review", "fills")}))
    if "--out" in a:
        Path(a[a.index("--out") + 1]).write_text(json.dumps(res, indent=1), encoding="utf-8")
