"""Hybrid search over the schema, the value index and learned knowledge.

Keyword ranking (SQLite FTS5 / BM25) always runs. If `fastembed` is installed, dense
vectors (snowflake-arctic-embed-s, 384-d, CPU/ONNX) are scored too, and the two ranked
lists are merged with Reciprocal Rank Fusion. See docs/07-retrieval.md.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Iterable

import numpy as np

from .store import Store

log = logging.getLogger(__name__)
EMBED_MODEL = "snowflake/snowflake-arctic-embed-s"
RRF_K = 60
_WORD = re.compile(r"[A-Za-z0-9]+")
_STOP = {"the", "a", "an", "of", "in", "on", "for", "to", "and", "or", "me", "show", "list", "all",
         "give", "which", "what", "who", "how", "many", "with", "by", "is", "are", "was", "were",
         "that", "this", "those", "these", "my", "our", "their", "please", "get", "find", "from", "do"}


def split_identifier(name: str) -> str:
    """'order_item.unit_price' -> 'order item unit price'; 'createdAt' -> 'created At'."""
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    return re.sub(r"[_.\-]+", " ", name)


def fts_query(text: str) -> str:
    """User words -> FTS5 OR-query of quoted tokens with prefix match. Never raises on odd input."""
    words = [w.lower() for w in _WORD.findall(split_identifier(text))]
    words = [w for w in words if w not in _STOP and len(w) > 1] or [w.lower() for w in _WORD.findall(text)][:6]
    return " OR ".join(f'"{w}"*' for w in dict.fromkeys(words)) or '""'


def rrf(*ranked: Iterable[str], k: int = RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for lst in ranked:
        for rank, key in enumerate(lst):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    return scores


class Embedder:
    """Lazy fastembed wrapper; `available` is False when the extra is not installed."""

    def __init__(self, enabled: bool = True):
        self.available = False
        self._model = None
        if not enabled:
            return
        try:
            import fastembed  # noqa: F401
            self.available = True
        except ImportError:
            log.info("fastembed not installed: keyword search only")

    def _get(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(EMBED_MODEL)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.array(list(self._get().embed(texts, batch_size=64)), dtype=np.float32)
        return vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9)


@lru_cache(maxsize=4)
def get_embedder(enabled: bool) -> Embedder:
    return Embedder(enabled)


class Index:
    def __init__(self, store: Store, embedder: Embedder):
        self.store = store
        self.embedder = embedder
        self._matrix: dict[str, tuple[list[str], np.ndarray]] = {}

    # ---- writes ------------------------------------------------------------------------
    def put_vectors(self, refs: list[str], texts: list[str]) -> None:
        if not self.embedder.available or not refs:
            return
        vecs = self.embedder.embed(texts)
        with self.store.tx() as db:
            db.executemany("INSERT OR REPLACE INTO embedding(ref, vector) VALUES(?, ?)",
                           [(r, v.tobytes()) for r, v in zip(refs, vecs)])
        self._matrix.clear()

    def drop_vectors(self, prefix: str) -> None:
        with self.store.tx() as db:
            db.execute("DELETE FROM embedding WHERE ref LIKE ?", (prefix + "%",))
        self._matrix.clear()

    # ---- reads -------------------------------------------------------------------------
    def _dense(self, prefix: str, query: str, top: int) -> list[str]:
        if not self.embedder.available:
            return []
        if prefix not in self._matrix:
            rows = self.store.all("SELECT ref, vector FROM embedding WHERE ref LIKE ?", (prefix + "%",))
            if not rows:
                return []
            self._matrix[prefix] = ([r["ref"] for r in rows],
                                    np.vstack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows]))
        refs, mat = self._matrix[prefix]
        q = self.embedder.embed([query])[0]
        sims = mat @ q
        order = np.argsort(-sims)[:top]
        return [refs[i] for i in order if sims[i] > 0.2]

    def search_schema(self, query: str, top: int = 12) -> list[dict]:
        rows = self.store.all(
            "SELECT kind, table_name, column_name, bm25(schema_fts) AS s FROM schema_fts "
            "WHERE schema_fts MATCH ? ORDER BY s LIMIT 60", (fts_query(query),))
        kw = [f"schema:{r['table_name']}.{r['column_name'] or ''}" for r in rows]
        fused = rrf(kw, self._dense("schema:", query, 60))
        out = []
        for ref, score in sorted(fused.items(), key=lambda x: -x[1])[:top]:
            table, _, column = ref.removeprefix("schema:").partition(".")
            out.append({"table": table, "column": column or None, "score": round(score, 4)})
        return out

    def search_values(self, text: str, top: int = 15) -> list[dict]:
        return self.store.all(
            "SELECT value, table_name AS \"table\", column_name AS \"column\", freq, bm25(value_fts) AS s "
            "FROM value_fts WHERE value_fts MATCH ? ORDER BY s LIMIT ?", (fts_query(text), top))

    def search_knowledge(self, query: str, visible_ids: set[str], top: int = 8) -> list[str]:
        if not visible_ids:
            return []
        rows = self.store.all(
            "SELECT id, bm25(knowledge_fts) AS s FROM knowledge_fts WHERE knowledge_fts MATCH ? "
            "ORDER BY s LIMIT 50", (fts_query(query),))
        kw = [f"knowledge:{r['id']}" for r in rows if r["id"] in visible_ids]
        dense = [r for r in self._dense("knowledge:", query, 50) if r.removeprefix("knowledge:") in visible_ids]
        fused = rrf(kw, dense)
        return [ref.removeprefix("knowledge:") for ref, _ in sorted(fused.items(), key=lambda x: -x[1])[:top]]
