"""Compare embedding models on schema retrieval: recall@5 of the gold tables (B-028).

    uv run python tools/embed_compare.py <state.db with a bootstrapped catalog> <cases.jsonl> [<cases.jsonl> ...]
        [--models a,b,...] [--out results.json]

For each model (and each with query/passage prefixes, "+qp"), the schema documents already in the
state file are re-embedded in a temporary copy, and for every case with a gold_sql the tables of that
SQL are looked up among the first 5 distinct tables of (a) dense search alone and (b) the hybrid
search the bot uses (keyword + dense, RRF). A cases file can be named "<file>:validated" (only
prompt_quality "question", the PO-validated ones) or "<file>:drafts" (asks draft_question;
agent-written, not PO-validated). No LLM calls.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from reportsbot.evals import load_cases
from reportsbot.retrieval import Embedder, Index, get_embedder
from reportsbot.safety import tables_in
from reportsbot.store import Store

MODELS = ["snowflake/snowflake-arctic-embed-s", "google/embeddinggemma-300m", "Qwen/Qwen3-Embedding-0.6B"]


def top_tables(refs: list[str], k: int = 5) -> list[str]:
    out: list[str] = []
    for r in refs:
        t = r.removeprefix("schema:").split(".", 1)[0]
        if t not in out:
            out.append(t)
    return out[:k]


def run(state: Path, case_files: list[str], models: list[str]) -> dict:
    sets = {}
    for spec in case_files:
        path, _, mode = spec.partition(":")
        dialect = "mysql" if "jms" in path else "sqlite"
        cases = [c for c in load_cases(path, use_drafts=mode == "drafts") if c.get("gold_sql")
                 and (mode != "validated" or c.get("prompt_quality") == "question")]
        sets[spec] = [(c["question"], set(tables_in(c["gold_sql"], dialect))) for c in cases]
    results = []
    for model in models:
        for asym in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                copy = Path(tmp) / "state.db"
                shutil.copy(state, copy)
                store = Store(copy)
                if model.startswith("lmstudio:") and asym:
                    continue  # LM Studio models get their own prefixes already (OpenAICompatEmbedder)
                index = Index(store, get_embedder(model) if model.startswith("lmstudio:") else Embedder(True, model, asym))
                rows = store.all("SELECT table_name, column_name, text FROM schema_fts")
                started = time.time()
                index.drop_vectors("schema:")
                index.put_vectors([f"schema:{r['table_name']}.{r['column_name'] or ''}" for r in rows],
                                  [r["text"][:1000] for r in rows])
                embed_s = time.time() - started
                row = {"model": model + ("+qp" if asym else ""), "docs": len(rows), "embed_seconds": round(embed_s, 1)}
                for spec, cases in sets.items():
                    dense = hybrid = total = 0
                    for q, gold in cases:
                        total += len(gold)
                        dense += len(gold & set(top_tables(index._dense("schema:", q, 60))))
                        hybrid += len(gold & set(top_tables([f"schema:{h['table']}." for h in
                                                             index.search_schema(q, top=40)])))
                    row[spec] = {"cases": len(cases), "dense_recall@5": round(dense / total, 3),
                                 "hybrid_recall@5": round(hybrid / total, 3)}
                results.append(row)
                print(json.dumps(row), flush=True)
                store.db.close()
    return {"run": time.strftime("%Y-%m-%d"), "state": str(state), "results": results}


if __name__ == "__main__":
    args = sys.argv[1:]
    out = args[args.index("--out") + 1] if "--out" in args else None
    models = args[args.index("--models") + 1].split(",") if "--models" in args else MODELS
    files = [a for i, a in enumerate(args[1:], 1) if not a.startswith("--") and args[i - 1] not in ("--out", "--models")]
    res = run(Path(args[0]), files, models)
    if out:
        Path(out).write_text(json.dumps(res, indent=1), encoding="utf-8")
