"""Do ReBo's checks catch a fan-out? Mutation test on gold reports (B-057).

    uv run python tools/fanout_mutants.py <folder/state.db> <gold.jsonl> [--out results.json]   (the file must be named state.db)
    (the reported database comes from rebo.yaml / REBO_CONFIG, as for the bot)

Fan-out is the most common structural error seen in evals: joining a table with several rows per row
of the report, so rows repeat or sums grow. For every gold report, each declared child table of a
table in its FROM clause (a foreign key pointing at that table's primary key) is joined in, without
changing the select list. A mutant is "real" when it returns different rows than the gold query. It is
"caught" when the validator's checks would object: the SQL trap check (sum over a repeated column),
the grain check (rows repeat per the entity key), or the metamorphic fan-out probe (safety.fanout_probes).
The probe is also run on every correct gold report, to count false alarms. No LLM.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import sqlglot
from sqlglot import exp

from rebo.agent import entity_key, sql_trap
from rebo.safety import fanout_probes
from rebo.evals import columns_match, load_cases
from rebo.service import App
from rebo.settings import get_settings


def mutants(sql: str, dialect: str, children: dict[str, list[tuple[str, str, str]]]):
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.ParseError:
        return
    sel = tree if isinstance(tree, exp.Select) else None
    if sel is None or not sel.args.get("from_"):
        return
    used = {t.name.lower() for t in sel.find_all(exp.Table)}
    for t in [sel.args["from_"].this, *(j.this for j in sel.args.get("joins") or [])]:
        if not isinstance(t, exp.Table):
            continue
        for child, ccol, pcol in children.get(t.name.lower(), []):
            if child in used:
                continue
            m = sel.copy().join(exp.to_table(child).as_("fo"), on=f"fo.{ccol} = {t.alias_or_name}.{pcol}")
            yield f"{t.name}->{child}", m.sql(dialect=dialect)


def run(state: Path, path: str) -> dict:
    app = App(get_settings().model_copy(update={"state_dir": state.parent, "state_url": ""}))
    dialect, pks = app.target.dialect, app.catalog.primary_keys
    children: dict[str, list[tuple[str, str, str]]] = {}
    for j in app.store.all("SELECT * FROM cat_join WHERE source='fk'"):
        children.setdefault(j["to_table"].lower(), []).append((j["from_table"].lower(), j["from_cols"], j["to_cols"]))
    rows, gold_alarms = [], []
    for c in load_cases(path):
        if not c.get("gold_sql"):
            continue
        try:
            gold = app._run_report_sql(c["gold_sql"])
        except Exception:  # gold reports that no longer run locally (protected columns, schema drift)
            continue
        for name, sql in mutants(c["gold_sql"], dialect, children):
            try:
                res = app._run_report_sql(sql)
            except Exception:
                continue
            real = not columns_match(gold.rows, res.rows)
            trap = sql_trap(sql, dialect, pks)
            key = entity_key(sql, dialect, pks)
            grain = bool(key and len(res.rows) > len({r[key[0]] for r in res.rows}))
            rows.append({"id": c["id"], "mutant": name, "real": real, "trap": bool(trap), "grain": grain,
                         "probe": fans_out(app, sql, res.rows)})
        gold_alarms.append({"id": c["id"], "probe_on_gold": fans_out(app, c["gold_sql"], gold.rows)})
    real = [r for r in rows if r["real"]]
    caught = [r for r in real if r["trap"] or r["grain"]]
    with_probe = [r for r in real if r["trap"] or r["grain"] or r["probe"]]
    false_alarm = [r for r in rows if not r["real"] and (r["trap"] or r["grain"] or r["probe"])]
    return {"run": time.strftime("%Y-%m-%d"), "mutants": len(rows), "real_errors": len(real),
            "caught_before": f"{len(caught)}/{len(real)}", "caught_with_probe": f"{len(with_probe)}/{len(real)}",
            "by_trap": sum(r["trap"] for r in real), "by_grain": sum(r["grain"] for r in real),
            "by_probe": sum(r["probe"] for r in real), "false_alarms_on_harmless_mutants": len(false_alarm),
            "probe_false_alarms_on_correct_gold": f"{sum(g['probe_on_gold'] for g in gold_alarms)}/{len(gold_alarms)}",
            "rows": rows}


def fans_out(app, sql: str, rows) -> bool:
    for _, probe in fanout_probes(sql, app.target.dialect):
        try:
            if not columns_match(rows, app._run_report_sql(probe).rows):
                return True
        except Exception:
            continue
    return False


if __name__ == "__main__":
    a = sys.argv[1:]
    out = a[a.index("--out") + 1] if "--out" in a else None
    res = run(Path(a[0]), a[1])
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    if out:
        Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
