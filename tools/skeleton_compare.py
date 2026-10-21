"""Would SQL-skeleton similarity find the right saved report better than the question text? (B-050)

    uv run python tools/skeleton_compare.py <state.db> <gold.jsonl> <eval results with agent SQL> [--out results.json]

Every gold report is saved, in a temporary copy of the state, as a shared example under its stored
question. Each evaluated case then looks for its own report among all of them, three ways:
  text      the bot's knowledge search with the question as asked (keyword + vectors, RRF)
  skeleton  skeleton similarity between the agent's SQL for that question and each saved query
  fused     reciprocal rank fusion of the two
and recall@1, recall@3 and MRR are reported. The agent's SQL comes from an eval run (e.g. with
--use-drafts, so the asked question differs from the stored one). No LLM calls.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from rebo.evals import load_cases
from rebo.knowledge import User
from rebo.retrieval import rrf
from rebo.safety import skeleton, skeleton_similarity
from rebo.service import App
from rebo.settings import get_settings


def ranks(order: list[str], own: str) -> int | None:
    return order.index(own) + 1 if own in order else None


def summarise(rs: list[int | None]) -> dict:
    n = len(rs)
    return {"recall@1": round(sum(r == 1 for r in rs) / n, 3), "recall@3": round(sum(r is not None and r <= 3 for r in rs) / n, 3),
            "mrr": round(sum(1 / r for r in rs if r) / n, 3)}


def run(state: Path, gold_path: str, results_path: str) -> dict:
    bank = [c for c in load_cases(gold_path) if c.get("gold_sql")]
    results = json.loads(Path(results_path).read_text())["cases"]
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(state, Path(tmp) / "state.db")
        app = App(get_settings().model_copy(update={"state_dir": Path(tmp), "state_url": ""}))
        admin = User("skeleton-compare", role="admin")
        ids, refused = {}, []
        for c in bank:
            try:  # reports the bot refuses to save (protected columns, SQL that no longer runs) are left out
                item = app.add_knowledge(admin, kind="example", title=c.get("title") or c["question"], question=c["question"], sql=c["gold_sql"])
                ids[c["id"]] = item["item"]["id"]
            except ValueError:
                refused.append(c["id"])
        bank = [c for c in bank if c["id"] in ids]
        visible = set(ids.values())
        dialect = app.target.dialect
        skel = {i: skeleton(c["gold_sql"], dialect) for c, i in ((c, ids[c["id"]]) for c in bank)}
        rows = []
        for r in results:
            own = ids.get(r["id"])
            if not own or not r.get("sql"):
                continue
            text = [x.removeprefix("knowledge:") for x in app.index.search_knowledge(r["question"], visible, top=len(visible))]
            draft = skeleton(r["sql"], dialect)
            by_shape = sorted(visible, key=lambda i: -skeleton_similarity(draft, skel[i]))
            fused = [k for k, _ in sorted(rrf(text, by_shape).items(), key=lambda x: -x[1])]
            rows.append({"id": r["id"], "matched": r["scores"].get("ExecutionMatch"), "text": ranks(text, own),
                         "skeleton": ranks(by_shape, own), "fused": ranks(fused, own)})
    out = {"run": time.strftime("%Y-%m-%d"), "bank": len(bank), "refused": refused, "cases": len(rows),
           **{k: summarise([x[k] for x in rows]) for k in ("text", "skeleton", "fused")}, "rows": rows}
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    out = args[args.index("--out") + 1] if "--out" in args else None
    pos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--out")]
    res = run(Path(pos[0]), pos[1], pos[2])
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    if out:
        Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
