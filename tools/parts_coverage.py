"""Could answers be composed from parts of other confirmed reports? Offline test of doc 26 §3 (B-055).

    uv run python tools/parts_coverage.py <cases.jsonl> <dialect> [--out results.json]

Each gold report is broken into parts with sqlglot (aliases resolved to table names):
  E entity (the FROM table)       J join (ON condition, operands in a fixed order)
  F filter (one WHERE conjunct)   M measure (an aggregate in the select list)
  D dimension (a GROUP BY expression)
For each report, leaving it out: how many of its parts appear in the other reports exactly, and how
many appear with only literal values changed (which ReBo already fills in). A report is "composable"
when every part is covered. No LLM, no database.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import sqlglot
from sqlglot import exp

from rebo.evals import load_cases


def _resolve(node: exp.Expression, aliases: dict[str, str]) -> exp.Expression:
    node = node.copy()
    for c in node.find_all(exp.Column):
        if c.table and c.table.lower() in aliases:
            c.set("table", exp.to_identifier(aliases[c.table.lower()]))
    return node


def _template(node: exp.Expression) -> exp.Expression:
    node = node.copy()
    for lit in list(node.find_all(exp.Literal)):
        lit.replace(exp.Placeholder())
    return node


def parts(sql: str, dialect: str) -> list[tuple[str, str, str]]:
    """(kind, exact, template) for each part of the outermost SELECT."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except sqlglot.errors.ParseError:
        return []
    sel = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if sel is None or not sel.args.get("from_"):
        return []
    sources = [sel.args["from_"].this, *(j.this for j in sel.args.get("joins") or [])]
    aliases = {t.alias_or_name.lower(): t.name.lower() for t in sources if isinstance(t, exp.Table)}
    out: list[tuple[str, exp.Expression]] = []
    base = sel.args["from_"].this
    if isinstance(base, exp.Table):
        out.append(("E", exp.to_identifier(base.name.lower())))
    for j in sel.args.get("joins") or []:
        on = j.args.get("on")
        if on is not None:
            on = _resolve(on, aliases)
            if isinstance(on, exp.EQ):  # a = b and b = a are the same join
                l, r = sorted([on.left.sql(), on.right.sql()])
                on = sqlglot.parse_one(f"{l} = {r}", read=dialect)
            out.append(("J", on))
    where = sel.args.get("where")
    if where is not None:
        conj = list(where.this.flatten()) if isinstance(where.this, exp.And) else [where.this]
        out += [("F", _resolve(c, aliases)) for c in conj]
    for e in sel.expressions:
        inner = e.this if isinstance(e, exp.Alias) else e
        if inner.find(exp.AggFunc):
            out.append(("M", _resolve(inner, aliases)))
    group = sel.args.get("group")
    if group is not None:
        out += [("D", _resolve(g, aliases)) for g in group.expressions]
    return [(k, n.sql(dialect=dialect).lower(), _template(n).sql(dialect=dialect).lower()) for k, n in out]


def run(path: str, dialect: str) -> dict:
    cases = [c for c in load_cases(path) if c.get("gold_sql")]
    each = {c["id"]: parts(c["gold_sql"], dialect) for c in cases}
    each = {k: v for k, v in each.items() if v}
    exact_count = Counter(p[1] for ps in each.values() for p in set(ps))
    tmpl_count = Counter(p[2] for ps in each.values() for p in set(ps))
    rows, by_kind = [], Counter()
    for cid, ps in each.items():
        mine_exact, mine_tmpl = Counter(p[1] for p in set(ps)), Counter(p[2] for p in set(ps))
        exact = [p for p in ps if exact_count[p[1]] - mine_exact[p[1]] > 0]
        valued = [p for p in ps if tmpl_count[p[2]] - mine_tmpl[p[2]] > 0]
        for k, *_ in ps:
            by_kind[(k, "all")] += 1
        for k, *_ in valued:
            by_kind[(k, "covered")] += 1
        rows.append({"id": cid, "parts": len(ps), "exact": len(exact), "with_values": len(valued),
                     "composable_exact": len(exact) == len(ps), "composable_with_values": len(valued) == len(ps)})
    n = len(rows)
    total = sum(r["parts"] for r in rows)
    return {
        "run": time.strftime("%Y-%m-%d"), "cases": path, "reports": n, "parts": total,
        "distinct_parts": len(exact_count), "parts_in_2plus_reports": sum(1 for v in exact_count.values() if v >= 2),
        "part_coverage_exact": round(sum(r["exact"] for r in rows) / total, 3),
        "part_coverage_with_values": round(sum(r["with_values"] for r in rows) / total, 3),
        "reports_composable_exact": f"{sum(r['composable_exact'] for r in rows)}/{n}",
        "reports_composable_with_values": f"{sum(r['composable_with_values'] for r in rows)}/{n}",
        "coverage_by_kind": {k: f"{by_kind[(k, 'covered')]}/{by_kind[(k, 'all')]}" for k in "EJFMD" if by_kind[(k, 'all')]},
        "rows": rows,
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args[args.index("--out") + 1] if "--out" in args else None
    res = run(args[0], args[1])
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    if out:
        Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
