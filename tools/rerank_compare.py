"""Does a cross-encoder reranker help schema retrieval? recall@5 of the gold tables (B-051).

    uv run python tools/rerank_compare.py <state.db with a bootstrapped catalog> <cases.jsonl[:validated]> ...
        [--models a,b,...] [--depth 30] [--out results.json]

For every case with a gold_sql: the bot's hybrid search (keyword + dense, RRF) gives its first `depth`
schema documents; each reranker (fastembed TextCrossEncoder, local ONNX) re-scores them against the
question; recall@5 counts gold tables among the first 5 distinct tables, before and after. Also
reports the reranking time per question. No LLM calls; the state file is only read.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fastembed.rerank.cross_encoder import TextCrossEncoder

from rebo.evals import load_cases
from rebo.retrieval import Embedder, Index
from rebo.safety import tables_in
from rebo.store import Store

MODELS = ["Xenova/ms-marco-MiniLM-L-6-v2", "Xenova/ms-marco-MiniLM-L-12-v2", "jinaai/jina-reranker-v1-turbo-en",
          "BAAI/bge-reranker-v2-m3-int8"]


def tables(refs: list[str], k: int = 5) -> list[str]:
    out: list[str] = []
    for r in refs:
        t = r.removeprefix("schema:").split(".", 1)[0]
        if t not in out:
            out.append(t)
    return out[:k]


def run(state: Path, specs: list[str], models: list[str], depth: int) -> dict:
    store = Store(state)
    index = Index(store, Embedder(True))
    docs = {f"schema:{r['table_name']}.{r['column_name'] or ''}": r["text"][:1000]
            for r in store.all("SELECT table_name, column_name, text FROM schema_fts")}
    results = []
    for spec in specs:
        path, _, mode = spec.partition(":")
        dialect = "mysql" if "jms" in path else "sqlite"
        cases = [(c["question"], set(tables_in(c["gold_sql"], dialect))) for c in load_cases(path)
                 if c.get("gold_sql") and (mode != "validated" or c.get("prompt_quality") == "question")]
        candidates = [[f"schema:{h['table']}.{h['column'] or ''}" for h in index.search_schema(q, top=depth)]
                      for q, _ in cases]
        total = sum(len(g) for _, g in cases)
        base = sum(len(g & set(tables(c))) for (_, g), c in zip(cases, candidates))
        row = {"cases": spec, "n": len(cases), "depth": depth, "hybrid_recall@5": round(base / total, 3)}
        for model in models:
            enc = TextCrossEncoder(model)
            hit, started = 0, time.time()
            for (q, gold), cand in zip(cases, candidates):
                scores = list(enc.rerank(q, [docs.get(r, r) for r in cand]))
                ranked = [r for _, r in sorted(zip(scores, cand), key=lambda x: -x[0])]
                hit += len(gold & set(tables(ranked)))
            row[model] = {"recall@5": round(hit / total, 3),
                          "ms_per_question": round(1000 * (time.time() - started) / max(len(cases), 1))}
        results.append(row)
        print(json.dumps(row), flush=True)
    return {"run": time.strftime("%Y-%m-%d"), "state": str(state), "results": results}


if __name__ == "__main__":
    args = sys.argv[1:]
    opt = lambda k, d: args[args.index(k) + 1] if k in args else d  # noqa: E731
    files = [a for i, a in enumerate(args[1:], 1) if not a.startswith("--")
             and args[i - 1] not in ("--out", "--models", "--depth")]
    res = run(Path(args[0]), files, opt("--models", ",".join(MODELS)).split(","), int(opt("--depth", "30")))
    if out := opt("--out", None):
        Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
