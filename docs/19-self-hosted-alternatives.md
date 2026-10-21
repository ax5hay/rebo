# 19 · Self-hosted, open-source alternatives (evaluated 2026-10-21)

> **These are suggestions, not decisions.** They reflect one research pass on 2026-10-21. Versions,
> licences and project health change. Before adopting anything listed here, the implementing agent or
> developer must research it again and look for newer alternatives, following the protocol in
> `AGENTS.md` §4 (re-verify on primary sources, check licence and maintenance, prototype behind a
> flag, measure with `tools/eval_run.py`, record the decision).

Question: are there better open-source components that run locally or in Docker (a powerful PC is
fine at first)? LLM inference is out of scope here (doc 20). Versions, dates, licences and archive
status were checked on GitHub/PyPI/Docker Hub on 2026-10-21. **[U]** = unverified.

**Short answer:** no open-source platform beats this design as a whole for a generic,
learn-from-users product. Several **components** are better at production scale and are planned as
opt-in swaps (doc 18 P2/P3), each behind at most one config key.

## 1. Whole platforms

| Project | Version / date | Licence | Verdict | Why |
|---|---|---|---|---|
| **WrenAI** | wrenai 0.16.0 (2026-10-16), wren-pydantic 0.3.1 | Apache-2.0 core (one AGPL file; check per path); GenBI UI commercial | **Borrow ideas** | Now a CLI/library: MDL semantic layer on DataFusion, LanceDB memory, `queries.yml`/`instructions.md` in git. Its semantic layer is hand-written YAML, the opposite of "minimal config". Worth borrowing: dry-plan validation, value profiling. `wren-pydantic` could be an optional tool provider. |
| **ktx** (Kaelio) | v0.16.0 npm (2026-07-03), active | Apache-2.0 | **Borrow ideas** | Join graph that resolves fan/chasm traps (doc 18 P1.7), contradiction flagging. Node CLI, YAML layer. |
| Vanna | 2.0.2; **archived 2026-03-29** | MIT | Avoid | Dead; we already have its best idea (retrieving confirmed question→SQL pairs) with a trust model it never had |
| DB-GPT | 0.8.2 (2026-08-26) | MIT | Keep ours | Large framework; old benchmark evidence only |
| Dataherald | last push 2024-07 | Apache-2.0 | Avoid | Dead |
| Chat2DB | 5.3.8 | Modified Apache: no external products / OEM | Avoid | Licence |
| MindsDB | pivoted to "MindsHub" | MIT | Not a fit | — |
| PyGWalker | 0.5.0.1 | Apache-2.0 | Optional add-on | Explore a result table visually |

Accuracy context: a 2026 on-prem study (arXiv 2606.29733) found **execution-guided self-correction**
(+1.2 to +4.4 points) the only consistent gain. That is what our output validator does, and doc 18
P1.2/P1.4/P1.7 build on it.

## 2. Embeddings and reranking

| Option | Version | Licence | Runs | Verdict |
|---|---|---|---|---|
| **fastembed** (in-process, current) | 0.9.0 | Apache-2.0 | CPU ONNX | **Keep for lean installs.** Switch the model from arctic-embed-s to **EmbeddingGemma-300m** (supported since 0.8.1) or Qwen3-Embedding-0.6B after an eval (doc 18 P2.3) |
| **HF TEI** | 1.9.4 (2026-09-15) | Apache-2.0 | Docker CPU/CUDA | **Adopt for production embeddings**: Qwen3-Embedding 0.6B (CPU) / 4B (GPU, about 8 GB). Does **not** serve Qwen3-Reranker (issue #643) |
| vLLM pooling | 0.32.0 | Apache-2.0 | GPU | Optional reranker host (`/v1/rerank`, Qwen3-Reranker) |
| Infinity | 0.0.78 | MIT for the Python packages; V3 under "Restricted MIT" | Docker | Optional single server for embed + rerank; check the licence |
| Ollama embeddings | 0.40.6 | MIT | — | Only if Ollama is already used |

Models (model-card numbers): Qwen3-Embedding 0.6B / 4B / 8B: MTEB-Eng v2 70.70 / 74.60 / 75.22 (Apache-2.0).
Qwen3-Reranker 0.6B / 4B: MTEB-R 65.80 / 69.76 vs 57.03 for bge-reranker-v2-m3. jina v4/v5 are not
commercially usable. Add a reranker only if evals show retrieval recall is the bottleneck.

## 3. State, search and vectors

| Option | Version | Licence | Verdict |
|---|---|---|---|
| SQLite + FTS5 + NumPy vectors (current) | stdlib | public domain | **Keep as default** (laptop, single instance) |
| **Postgres 18 + pgvector 0.8.7 + pg_textsearch 1.5.1** | pgvector 0.8.7 (2026-10, CVE fix), pg_textsearch 1.5.1 (2026-10-02) | PostgreSQL | **Adopt for production** (doc 18 P2.1): real BM25 + HNSW + row-level security + ACID with the knowledge rows in one store, RRF in SQL |
| ParadeDB pg_search | 0.26.2 | **AGPL-3.0** | Avoid in a distributed product |
| Qdrant | 1.19.2 | Apache-2.0 | Good engine, but a second store without transactions alongside knowledge rows: not needed |
| LanceDB | 0.40.0 | Apache-2.0 | Lean embedded alternative (WrenAI uses it) |
| Weaviate / Milvus / OpenSearch / Meilisearch / Typesense | — | mixed (Typesense GPL-3.0; Meilisearch EE BUSL) | Not needed |
| sqlite-vec | 0.1.9 (2026-03) | MIT/Apache | Pre-1.0, slow-moving; not needed at our size |

## 4. LLM gateway

| Option | Version | Licence | Verdict |
|---|---|---|---|
| Pydantic AI built-ins (current) | 2.58.0 | MIT | **Keep**: FallbackModel, UsageLimits (incl. cost), prompt caching, concurrency limiter, AG-UI. Enough for one app |
| Bifrost (Maxim) | 2.3.2 | Apache-2.0 | **Best optional add-on** if many apps need shared budgets / virtual keys |
| LiteLLM proxy | 1.106.1 | MIT + enterprise dir | Optional; use the pinned Docker image (PyPI 1.82.7–1.82.8 were malicious on 2026-03-24) |
| Portkey gateway | 1.15.2 | MIT | Watch |
| TensorZero | **archived** 2026-06-12 | — | Avoid |
| Helicone | maintenance mode | — | Avoid |

## 5. Caching

- **Never a semantic answer cache for SQL**: "Q3" vs "Q4" or another tenant's question can match and
  return wrong data. Confirmed-example retrieval is the safe form of semantic reuse.
- **Exact cache** keyed by normalised question + knowledge version + user scope + SQL hash
  (doc 18 P2.6), in Postgres or Valkey 9.x (BSD).
- **Prompt caching**: stable prefix first (doc 18 P1.8). GPTCache is dead (last release 2024-08).

## 6. Observability and evals

| Option | Version | Licence | Footprint | Verdict |
|---|---|---|---|---|
| **Arize Phoenix** | 20.23.0 | ELv2 (server) | 1 container, SQLite/Postgres | **Adopt** (doc 18 P3.2); ELv2 forbids offering it as a hosted service |
| MLflow tracing | 3.17.1 | Apache-2.0 | 1 server | Fully open alternative (`mlflow.pydantic_ai.autolog()`) |
| Langfuse | 4.66.0 | MIT + ee | Postgres + ClickHouse + Redis + S3 (~16 GB) | Too heavy |
| Opik / OpenLIT | — | Apache-2.0 | ClickHouse-based | Too heavy |
| pydantic-evals (current) | 2.58.0 | MIT | in-process | **Keep** |
| promptfoo | — | MIT | Node | Optional for red-teaming (OpenAI acquisition announced 2026-03) |

## 7. Durable execution

DBOS 3.3.0 (MIT, a library on SQLite/Postgres, Pydantic AI `DBOSDurability`) is the right choice
**when** scheduled or long report runs arrive (doc 18 P2.5). Temporal (cluster) and Hatchet (engine
+ Postgres) are too heavy; Celery/Dramatiq/arq are unnecessary.

## 8. Chat UI

| Option | Verdict |
|---|---|
| **assistant-ui** (MIT, `@assistant-ui/react` 0.15.30) on Pydantic AI's **AG-UI** adapter | **Adopt for the product UI** (doc 18 P3.1): tool-UI patterns cover tables, confirm/fix buttons, option and follow-up chips |
| CopilotKit (MIT, 1.79.1) | Alternative with native Pydantic AI / AG-UI support |
| NiceGUI 3.18 (current) | **Keep** for the curator/admin UI and local testing |
| Open WebUI | Custom licence with a branding clause above 50 users; awkward for custom widgets |
| LibreChat | General chat app, not a reports UI |
| Chainlit | Archived |
| Streamlit / Gradio | Rerun model is weak for human-in-the-loop flows |

## 9. Authentication for standalone installs

**oauth2-proxy 7.15.5** (MIT) in front of the bot pointing at the customer's IdP is the default; the
bot then uses `auth.mode: headers`. Without an IdP: **Pocket ID 2.18** (passkeys, SQLite, one
container). Authelia if passwords/TOTP are required. Keycloak and Authentik are heavier than needed.

## 10. Synthetic data

SDV 2.0.0 is BUSL-1.1 and its schema-only synthesizer is Enterprise-only, so it is not a fit.
Snowfakery is archived and Synth is stale. **NeMo Data Designer 0.9.5** (Apache-2.0) can add
conditional (correlated) columns and LLM-written text, and can point at LM Studio **[U]**. Keep
`tools/synth` for structure and keys; add a per-table correlation spec or Data Designer for
realistic cross-column distributions (doc 18, synth follow-up).

## 11. Recommended stacks

**Lean (laptop, default today):** one process: bot (FastAPI + Pydantic AI + sqlglot) with SQLite
FTS5 + fastembed + RRF, NiceGUI, pydantic-evals. About 1.5–2.5 GB RAM, no GPU. Optional Phoenix
container (about 0.5 GB). The test MySQL container adds about 0.5–1 GB.

**Production (docker compose), sizes approximate [U]:**

| Service | Image | RAM / VRAM |
|---|---|---|
| bot-api | ours | ~1 GB |
| web (assistant-ui build) | nginx | ~50 MB |
| postgres (state, knowledge, BM25, vectors, DBOS) | `pgvector/pgvector:0.8.7-pg18` + pg_textsearch 1.5.1 | 1–2 GB |
| embeddings | `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9` (Qwen3-Embedding-0.6B) | ~2 GB CPU (GPU 4B: ~8–10 GB VRAM) |
| reranker (optional) | `vllm/vllm-openai` + Qwen3-Reranker-0.6B | ~3–4 GB VRAM |
| valkey (exact cache, rate limits; optional) | `valkey/valkey:9.1` | ~200 MB |
| phoenix | `arizephoenix/phoenix:version-20.23.0` | 0.5–1 GB |
| oauth2-proxy (+ pocket-id) | `quay.io/oauth2-proxy/oauth2-proxy:v7.15.5` | ~50 MB |
| LM Studio (host, optional, offline LLM) | — | 16–24 GB VRAM for 20–35B Q4 models (doc 20) |

Total without a local LLM: about 6–8 GB RAM, 0–14 GB VRAM.

Sources: github.com/Canner/WrenAI · github.com/Kaelio/ktx · github.com/huggingface/text-embeddings-inference (issue 643) ·
github.com/QwenLM/Qwen3-Embedding · github.com/timescale/pg_textsearch · postgresql.org/about/news/pgvector-087-released-3392 ·
qdrant.tech/blog/qdrant-1.19.x · docs.litellm.ai/blog/security-update-march-2026 · arize.com/docs/phoenix/self-hosting/license ·
langfuse.com/self-hosting · pydantic.dev/docs/ai/integrations/{ui,durable_execution} · docs.dbos.dev · github.com/NVIDIA-NeMo/DataDesigner ·
docs.sdv.dev (DayZSynthesizer) · github.com/OtterMind/Chat2DB (LICENSE) · docs.openwebui.com/license · arxiv.org/abs/2606.29733
