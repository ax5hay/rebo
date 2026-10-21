import json
import sqlite3

import pytest


def test_bootstrap_profiles_and_indexes(app):
    t = app.store.one("SELECT * FROM cat_table WHERE name='customer'")
    assert t["rows"] == 40
    status = app.store.one("SELECT * FROM cat_column WHERE table_name='customer' AND name='status'")
    assert {v["value"] for v in json.loads(status["top_values"])} == {"active", "paused", "closed"}


def test_secret_columns_detected_by_name_and_value(app):
    assert ("customer", "password_hash") in app.catalog.sensitive
    col = app.store.one("SELECT top_values FROM cat_column WHERE table_name='customer' AND name='password_hash'")
    assert col["top_values"] is None  # values of protected columns are never stored


def test_declared_join_found(app):
    joins = {(j["from_table"], j["from_cols"], j["to_table"], j["source"])
             for j in app.store.all("SELECT * FROM cat_join")}
    assert ("orders", "customer_id", "customer", "fk") in joins
    assert app.catalog.join_path("orders", "customer")[0]["source"] == "fk"


def test_value_index_finds_stored_spelling(app):
    hits = app.index.search_values("paused customers")
    assert any(h["value"] == "paused" and h["table"] == "customer" for h in hits)


def test_schema_search_ranks_relevant_table(app):
    hits = app.index.search_schema("order amount")
    assert hits and hits[0]["table"] == "orders"


def test_describe_hides_protected_values(app):
    d = app.catalog.describe("customer")
    secret = next(c for c in d["columns"] if c["name"] == "password_hash")
    assert secret.get("protected") and "values" not in secret


def test_target_session_is_read_only(app):
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        app.target.run("DELETE FROM customer", max_rows=1)


def test_embeddings_setting_selects_the_embedder(app):
    import httpx2
    import numpy as np

    from rebo.retrieval import Embedder, TEIEmbedder, get_embedder
    assert type(get_embedder(True)) is Embedder and get_embedder(True).model_name.startswith("snowflake/")
    assert get_embedder(False).available is False
    assert get_embedder("google/embeddinggemma-300m").model_name == "google/embeddinggemma-300m"
    assert isinstance(get_embedder("http://tei:80"), TEIEmbedder)
    calls = []

    def tei(request):
        texts = json.loads(request.content)["inputs"]
        calls.append(len(texts))
        return httpx2.Response(200, json=[[float(len(t)), 1.0] for t in texts])

    emb = TEIEmbedder("http://tei:80/", client=httpx2.Client(transport=httpx2.MockTransport(tei)))
    vecs = emb.embed([f"text {i}" for i in range(40)])
    assert calls == [32, 8] and vecs.shape == (40, 2) and np.allclose(np.linalg.norm(vecs, axis=1), 1.0)


def test_lmstudio_embeddings_use_the_openai_compatible_endpoint_with_nomic_prefixes():
    import httpx2

    from rebo.retrieval import OpenAICompatEmbedder, get_embedder
    assert isinstance(get_embedder("lmstudio:text-embedding-nomic-embed-text-v1.5"), OpenAICompatEmbedder)
    sent = []

    def lm(request):
        body = json.loads(request.content)
        sent.append(body)
        return httpx2.Response(200, json={"data": [{"index": i, "embedding": [1.0, float(i)]}
                                                   for i, _ in enumerate(body["input"])]})

    emb = OpenAICompatEmbedder("http://127.0.0.1:1234/v1", "text-embedding-nomic-embed-text-v1.5",
                               client=httpx2.Client(transport=httpx2.MockTransport(lm)))
    emb.embed(["customer status"], kind="query")
    emb.embed(["table customer"], kind="passage")
    assert [b["input"][0] for b in sent] == ["search_query: customer status", "search_document: table customer"]
    assert sent[0]["model"] == "text-embedding-nomic-embed-text-v1.5"
