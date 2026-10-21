"""Hybrid search over the schema, the value index and learned knowledge.

Keyword ranking (SQLite FTS5 / BM25) always runs. If `fastembed` is installed, dense
vectors (snowflake-arctic-embed-s, 384-d, CPU/ONNX) are scored too, and the two ranked
lists are merged with Reciprocal Rank Fusion. See docs/07-retrieval.md.
"""
from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

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

    def __init__(self, enabled: bool = True, model: str = EMBED_MODEL, asymmetric: bool = False):
        """asymmetric: embed questions with the model's query prefix and documents with its passage
        prefix (fastembed query_embed / passage_embed) instead of the same plain embedding for both."""
        self.available = False
        self._model = None
        self.model_name, self.asymmetric = model, asymmetric
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
            # An offline bundle ships the model in models/fastembed (tools/export_bundle.py --with-models).
            bundled = Path(__file__).resolve().parents[2] / "models" / "fastembed"
            cache = os.environ.get("FASTEMBED_CACHE_PATH") or (str(bundled) if bundled.is_dir() else None)
            self._model = TextEmbedding(self.model_name, cache_dir=cache)
        return self._model

    def embed(self, texts: list[str], kind: str = "passage") -> np.ndarray:
        m = self._get()
        if not self.asymmetric:
            out = m.embed(texts, batch_size=64)
        else:
            out = m.query_embed(texts) if kind == "query" else m.passage_embed(texts, batch_size=64)
        vecs = np.array(list(out), dtype=np.float32)
        return vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9)


class TEIEmbedder(Embedder):
    """Embeddings from a Text Embeddings Inference server (`embeddings: http://tei:80`): POST /embed."""

    def __init__(self, url: str, client: Any = None):
        self.available, self._model, self.asymmetric = True, None, False
        self.model_name, self.url = url, url.rstrip("/")
        self._client = client

    def embed(self, texts: list[str], kind: str = "passage") -> np.ndarray:
        import httpx2
        client = self._client or httpx2.Client(timeout=60)
        out: list[list[float]] = []
        for i in range(0, len(texts), 32):
            r = client.post(f"{self.url}/embed", json={"inputs": texts[i:i + 32], "truncate": True})
            r.raise_for_status()
            out += r.json()
        vecs = np.array(out, dtype=np.float32)
        return vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9)


class OpenAICompatEmbedder(Embedder):
    """Embeddings from an OpenAI-compatible /embeddings endpoint, e.g. LM Studio
    (`embeddings: lmstudio:text-embedding-nomic-embed-text-v1.5`, server at lmstudio_url)."""

    # Models trained with task prefixes need them on both sides (model card of nomic-embed-text).
    PREFIXES = {"nomic-embed": ("search_query: ", "search_document: ")}

    def __init__(self, base_url: str, model: str, client: Any = None):
        self.available, self._model, self.asymmetric = True, None, True
        self.model_name, self.url, self._client = model, base_url.rstrip("/"), client
        self.prefix = next((v for k, v in self.PREFIXES.items() if k in model), ("", ""))

    def embed(self, texts: list[str], kind: str = "passage") -> np.ndarray:
        import httpx2
        client = self._client or httpx2.Client(timeout=120)
        pre = self.prefix[0] if kind == "query" else self.prefix[1]
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            r = client.post(f"{self.url}/embeddings", json={"model": self.model_name,
                                                            "input": [pre + t for t in texts[i:i + 64]]})
            r.raise_for_status()
            out += [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]
        vecs = np.array(out, dtype=np.float32)
        return vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-9)


@lru_cache(maxsize=4)
def get_embedder(setting: bool | str, lmstudio_url: str = "http://127.0.0.1:1234/v1") -> Embedder:
    """`embeddings` setting: true = the default local model, false = keyword search only, a fastembed
    model name, `lmstudio:<embedding model id>`, or an http(s):// URL of a TEI server."""
    if isinstance(setting, str) and setting.startswith("lmstudio:"):
        return OpenAICompatEmbedder(lmstudio_url, setting.split(":", 1)[1])
    if isinstance(setting, str) and setting.startswith(("http://", "https://")):
        return TEIEmbedder(setting)
    if isinstance(setting, str) and setting.strip().lower() not in ("true", "false", ""):
        return Embedder(True, setting.strip())
    return Embedder(setting is True or str(setting).lower() == "true")


def _pgvec(v: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v.tolist()) + "]"


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
            if self.store.pgvector:  # also as a pgvector value, searched in the database
                db.executemany("INSERT INTO embedding(ref, vector, vec) VALUES(?, ?, ?::vector) ON CONFLICT(ref) DO "
                               "UPDATE SET vector=excluded.vector, vec=excluded.vec",
                               [(r, v.tobytes(), _pgvec(v)) for r, v in zip(refs, vecs)])
            else:
                db.executemany("INSERT INTO embedding(ref, vector) VALUES(?, ?) ON CONFLICT(ref) DO UPDATE SET "
                               "vector=excluded.vector",
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
        if self.store.pgvector:  # cosine distance in the database: every process sees the same vectors
            q = _pgvec(self.embedder.embed([query], kind="query")[0])
            rows = self.store.all("SELECT ref FROM embedding WHERE ref LIKE ? AND vec IS NOT NULL AND "
                                  "1 - (vec <=> ?::vector) > 0.2 ORDER BY vec <=> ?::vector LIMIT ?",
                                  (prefix + "%", q, q, top))
            return [r["ref"] for r in rows]
        if prefix not in self._matrix:
            rows = self.store.all("SELECT ref, vector FROM embedding WHERE ref LIKE ?", (prefix + "%",))
            if not rows:
                return []
            self._matrix[prefix] = ([r["ref"] for r in rows],
                                    np.vstack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows]))
        refs, mat = self._matrix[prefix]
        q = self.embedder.embed([query], kind="query")[0]
        sims = mat @ q
        order = np.argsort(-sims)[:top]
        return [refs[i] for i in order if sims[i] > 0.2]

    def search_schema(self, query: str, top: int = 12) -> list[dict]:
        rows = self.store.match("schema_fts", fts_query(query), "kind, table_name, column_name", limit=60)
        kw = [f"schema:{r['table_name']}.{r['column_name'] or ''}" for r in rows]
        fused = rrf(kw, self._dense("schema:", query, 60))
        out = []
        for ref, score in sorted(fused.items(), key=lambda x: -x[1])[:top]:
            table, _, column = ref.removeprefix("schema:").partition(".")
            out.append({"table": table, "column": column or None, "score": round(score, 4)})
        return out

    def search_values(self, text: str, top: int = 15) -> list[dict]:
        return self.store.match("value_fts", fts_query(text),
                                'value, table_name AS "table", column_name AS "column", freq', limit=top)

    def masked_query(self, text: str, siblings: int = 30) -> str | None:
        """Question masking (DAIL-SQL): a word that is a stored value stands for its column, so it is
        replaced by that column's common values. "paused customers" then also matches an example saved
        for "active customers". None when no word is a stored value."""
        words = [w.strip('"*') for w in fts_query(text).split(" OR ")]
        out, masked = [], False
        for w in words:
            cols = {(r["table_name"], r["column_name"]) for r in self.store.match(
                "value_fts", f'"{w}"', "value, table_name, column_name", limit=50) if r["value"].strip().lower() == w}
            if not cols:
                out.append(w)
                continue
            masked = True
            for t, c in sorted(cols):
                out += [v for r in self.store.all(
                    "SELECT value FROM value_fts WHERE table_name=? AND column_name=? ORDER BY freq DESC LIMIT ?",
                    (t, c, siblings)) for v in _WORD.findall(r["value"].lower())]
        return " OR ".join(f'"{w}"' for w in dict.fromkeys(out)) if masked else None

    def search_knowledge(self, query: str, visible_ids: set[str], top: int = 8) -> list[str]:
        if not visible_ids:
            return []
        def keyword(fts: str) -> list[str]:
            rows = self.store.match("knowledge_fts", fts, "id", limit=50)
            return [f"knowledge:{r['id']}" for r in rows if r["id"] in visible_ids]
        kw = keyword(fts_query(query))
        masked = keyword(m) if (m := self.masked_query(query)) else []
        dense = [r for r in self._dense("knowledge:", query, 50) if r.removeprefix("knowledge:") in visible_ids]
        fused = rrf(masked, kw, dense)  # masked first: on a tie it wins (it matched the value's role too)
        return [ref.removeprefix("knowledge:") for ref, _ in sorted(fused.items(), key=lambda x: -x[1])[:top]]
