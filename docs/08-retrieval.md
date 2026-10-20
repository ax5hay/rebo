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

## 5. What is deliberately not here (yet)

- **A cross-encoder reranker.** fastembed has `ms-marco-MiniLM-L-6-v2` (0.08 GB). Add it if
  retrieval misses show up in the eval traces (doc 15).
- **Question masking for example retrieval** (DAIL-SQL masks schema words in questions before
  matching; 82.0 vs 79.9 execution accuracy on Spider-dev). Easy follow-up: mask the words that hit
  `schema_fts` before searching `knowledge_fts`.
- **MinHash/LSH over values.** FTS5 prefix search covers the categorical values profiled here.
  LSH matters for high-cardinality free text, which is intentionally not indexed.
