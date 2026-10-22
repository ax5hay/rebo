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


def test_dense_search_on_both_state_backends(app):
    """Vectors written and searched through the real Index: in-process on SQLite, pgvector on Postgres."""
    import numpy as np

    from rebo.retrieval import Embedder

    class Words(Embedder):  # deterministic toy embedder: one dimension per known word
        VOCAB = ["customer", "status", "order", "amount", "note", "paused"]

        def __init__(self):
            self.available, self._model, self.asymmetric, self.model_name = True, None, False, "toy"

        def embed(self, texts, kind="passage"):
            v = np.array([[float(w in t.lower()) for w in self.VOCAB] for t in texts], dtype=np.float32) + 1e-3
            return v / np.linalg.norm(v, axis=1, keepdims=True)

    app.index.embedder = Words()
    app.index._matrix.clear()
    app.index.put_vectors(["schema:customer.status", "schema:orders.amount", "schema:note.body"],
                          ["customer status", "order amount", "note body"])
    assert app.index._dense("schema:", "paused customer status", 3)[0] == "schema:customer.status"
    assert app.index._dense("schema:", "order amount", 1) == ["schema:orders.amount"]
    if app.store.dialect == "postgresql":
        assert app.store.pgvector and app.store.one(
            "SELECT COUNT(*) AS n FROM embedding WHERE vec IS NOT NULL")["n"] == 3


def test_value_search_falls_back_to_spelling_when_full_text_finds_nothing(app):
    hits = app.index.search_values("shiped")                     # misspelled; FTS finds no token
    assert hits and hits[0]["value"] == "shipped" and hits[0]["table"] == "orders" and "spelled like" in hits[0]["match"]
    assert app.index.search_values("zzzzqqq") == []                # nothing close: nothing invented
    assert "match" not in app.index.search_values("paused")[0]     # exact hits stay exact


def test_join_path_survives_ties_between_equal_paths(app):
    # two learned joins of equal cost between the same tables used to make the heap compare dicts
    learned = [{"from_table": "orders", "from_cols": "customer_id", "to_table": "customer", "to_cols": "customer_id", "source": "learned"},
               {"from_table": "note", "from_cols": "author_id", "to_table": "customer", "to_cols": "customer_id", "source": "learned"},
               {"from_table": "note", "from_cols": "author_id", "to_table": "orders", "to_cols": "customer_id", "source": "learned"}]
    path = app.catalog.join_path("note", "customer", learned)
    assert path is not None and len(path) == 1


def test_compact_describe_keeps_the_facts_in_one_line_per_column(app):
    full, compact = app.catalog.describe("customer"), app.catalog.describe_compact("customer")
    assert len(compact["columns"]) == len(full["columns"]) and compact["joins"] == full["joins"]
    status = next(line for line in compact["columns"] if line.startswith("status"))
    assert "paused" in status and "distinct" in status
    assert any("PROTECTED" in line for line in compact["columns"])        # password_hash stays marked
    import json
    assert len(json.dumps(compact)) < len(json.dumps(full))


def test_protected_columns_are_secrets_not_ids_flags_or_customer_codes():
    from rebo.catalog import _secret_column
    col = lambda name, typ="varchar(80)": {"name": name, "type": typ}  # noqa: E731
    assert _secret_column(col("password_hash"), [], [])
    assert _secret_column(col("api_token"), [], [])
    assert _secret_column(col("bank_account_no"), [], ["377568586860"])
    assert _secret_column(col("pan_number"), [], ["ABCPE1234F"])
    assert _secret_column(col("account_number"), [], ["50200019283746", "DE89370400440532013000"])   # bank accounts
    assert not _secret_column(col("account_number"), [], ["CUS-000001", "CUS-000002"])             # customer codes
    assert not _secret_column(col("api_key_id", "integer"), ["api_key_id"], [])                    # an identifier
    assert not _secret_column(col("token_id", "integer"), [], [])
    assert not _secret_column(col("mfa_enabled", "boolean"), [], [])                              # a yes/no flag
