# 08 · Retrieval

Code: `src/reportsbot/retrieval.py`. Three corpora, all in `state.db`:

| Corpus | Table | Rows (JMS local) | Searched by |
|---|---|---|---|
| Schema docs (one per table + one per column) | `schema_fts` + `embedding` (`schema:` refs) | 207 + 2,769 | `search_schema`, `_context_block` likely tables |
| Stored values of categorical columns | `value_fts` | 37,226 | `search_values`, `_context_block` value matches |
| Learned knowledge | `knowledge_fts` + `embedding` (`knowledge:` refs) | grows with use | `search_knowledge`, `_context_block` learned knowledge |

## 1. Keyword ranking: SQLite FTS5 + BM25

- Tokenisers: `porter unicode61` for schema and knowledge (stemming: "orders" matches "order");
  `unicode61` without stemming for values (stored spellings must match literally).
- `fts_query(text)`:
  1. split identifiers (`created_at` → `created at`, `caseType` → `case Type`);
  2. take alphanumeric words, lower-case them, and drop stop-words (`show`, `list`, `me`, `all`, `which`, …) and 1-letter words;
  3. quote each word and add a prefix star: `"surrog"* OR "screen"*`. Quoting means user input can
     never inject FTS syntax; the prefix star tolerates plurals and partial words.
- `ORDER BY bm25(...)` (lower is better), top 50–60 candidates.

## 2. Dense ranking (optional)

- `fastembed` + `snowflake/snowflake-arctic-embed-s`: 384-d, ONNX on CPU, 0.13 GB download on
  first use, MTEB retrieval NDCG@10 51.98 (best quality per byte among the CPU options in fastembed 0.9).
- Vectors are L2-normalised float32 BLOBs. Search is brute-force `matrix @ query` in NumPy, with the
  matrix cached in memory per prefix. That is a few milliseconds for 3,000 rows. sqlite-vec (pre-v1)
  or LanceDB become worth it past about 100k items.
- Hits below cosine 0.2 are dropped.
- Disabled with `REPORTSBOT_EMBEDDINGS=false`, or automatically when the `embed` extra is not
  installed. Everything still works on BM25 alone; the offline tests run that way.

## 3. Fusion: Reciprocal Rank Fusion

```python
def rrf(*ranked, k=60):
    score[key] += 1 / (k + rank + 1)   # for every list the key appears in
```

k=60 is the constant from the original RRF paper. Fusion needs no score calibration between BM25
and cosine, which is why it is the default in hybrid search (sqlite-vec + FTS5 write-up, ktx's
four retrieval lanes).

## 4. Knowledge ranking after fusion

`Knowledge.search(user, query, top)`:
1. visible ids only (doc 05 §2),
2. fused retrieval → top N ids,
3. sort: `verified` first, then the user's own (`active`/`proposed`), then by `confirmations` descending,
4. dedupe `term`/`note` by `(kind, lower(title))`: a shared definition hides the user's own
   conflicting version until a curator decides.

## 4b. Embedding model comparison (B-028, 2026-10-21)

`tools/embed_compare.py` re-embeds the JMS catalogue's 2,976 schema documents (207 tables, from a
bootstrapped `state.db`) with each model and measures **recall@5 of the gold tables**: the share of
the tables in each gold SQL that appear among the first 5 distinct tables of dense search alone and
of the hybrid search the bot uses (keyword + dense, RRF). No LLM. Results:
`fixtures/jms_staging/embed_compare_2026-10-21.json`.

| Model (fastembed 0.9.0, CPU) | Size | Embed 2,976 docs | Dense, 12 validated / 67 drafts | **Hybrid**, 12 validated / 67 drafts |
|---|---|---|---|---|
| snowflake-arctic-embed-s (default) | 0.13 GB | 37 s | 0.448 / 0.382 | **0.621** / 0.471 |
| google/embeddinggemma-300m | 1.24 GB | 134 s | 0.552 / 0.534 | 0.552 / 0.534 |
| Qwen/Qwen3-Embedding-0.6B | 2.38 GB | 350 s | 0.414 / 0.445 | 0.517 / 0.534 |

"Validated" = the 12 PO-validated questions; "drafts" = the 67 agent-written draft questions (B-014,
not validated, and written from the SQL, so they may echo its words). Query/passage prefixes
(`asymmetric=True`) gave identical numbers for all three models: fastembed 0.9.0 applies none to
these. **Verdict: keep arctic-embed-s.** On the validated set it is best in the hybrid search the bot
actually uses, and it is 10–18× smaller and 4–9× faster; the larger models only win on unvalidated
drafts. Caveats: 12 questions is a small sample, and the local catalogue has no rows (no value lists
in the documents). Re-run when B-015 adds validated questions. TEI (`embeddings: http://…`) was not
run here: its CPU image is amd64-only (this machine is arm64).

## 5. What is deliberately not here (yet)

*Question masking moved out of this list: it is built (B-009, 2026-10-21).* `Index.masked_query`:
a question word that is exactly a stored value (`value_fts`) stands for its column, so it is
replaced by that column's 30 most frequent values; other words stay. `search_knowledge` fuses three
rankings with RRF: masked keyword, plain keyword, dense (masked first, so it wins ties). "paused
customers" now ranks the example saved for "active customers" first, and "paused" alone finds it.
Schema words are not masked: they already match literally. Source: DAIL-SQL masks domain words
before matching examples (82.0 vs 79.9 execution accuracy on Spider-dev). Not measured on our eval
sets (needs an LLM key and saved examples).

- **A cross-encoder reranker.** fastembed has `ms-marco-MiniLM-L-6-v2` (0.08 GB). Add it if
  retrieval misses show up in the eval traces (doc 15).
- **MinHash/LSH over values.** FTS5 prefix search covers the categorical values profiled here.
  LSH matters for high-cardinality free text, which is intentionally not indexed.
