# 16 · Research basis (checked 2026-10-21)

Versions were checked on PyPI/GitHub on 2026-10-21. Benchmark numbers come from the cited
leaderboards and papers. Items marked *(unverified)* came only from secondary sources.

## 1. Text-to-SQL state of the art

- **Spider 2.0** (spider2-sql.github.io): Lite top 76.23 (Tianqiong Data Agent + GLM 5.2); the open
  source ktx (Kaelio, Apache-2.0) is at 73.67. Academic baselines are much lower (ProSPy 60.15 with
  Claude Opus 4.5, no voting).
- **Annotation-error caution:** CIDR 2026 (Jin et al.) found 66.1% of the 121 Spider2-Snow tasks with
  released gold SQL mis-annotated; arXiv 2601.08778 reports 52.8% for BIRD Mini-Dev. Leaderboard
  scores in the 90s are suspect, so we evaluate on our own confirmed questions (doc 11).
- **BIRD** (bird-bench.github.io): test execution accuracy top 82.95 (GrainSQL, 2026-09-26); human 92.96.
- **Interactive:** BIRD-Interact (ICLR 2026 oral). Best models solve about 16–24%, so interaction is hard
  and clarifications must be targeted.
- **Recurring winning techniques:** agentic exploration with probe queries (ReFoRCE), data profiling
  (ProSPy, AskData), multiple candidates + selection (CHASE-SQL, Agentar), execution-guided repair,
  critics. Applied here: exploration tools, profiling, execution-checked output; candidates/critic
  are on the roadmap for low-confidence turns.

## 2. Schema linking and metadata

- **Automatic metadata extraction** (Shkapenyuk, Srivastava, Johnson, Ghane; arXiv 2505.19988): profile
  statistics + LLM summaries beat BIRD's hand-written metadata; combining them was best → doc 03.
- **AutoLink** (AAAI-26, arXiv 2511.17190): iterative schema exploration that never sees the whole schema,
  with 97.4% strict recall on BIRD-dev → `search_schema` + `describe_table` instead of a schema dump.
- **Value retrieval:** CHESS (MinHash LSH over DB values), ktx (embeddings + value dictionary + BM25 +
  token overlap fused with RRF) → `value_fts` + RRF (doc 08).
- **Semantic layers:** Anthropic's data team (claude.com blog, 2026-06-03) found auto-generated metric
  definitions *net-negative* vs a small curated layer; people's corrections were harvested into evals.
  arXiv 2604.25149: a 4 KB semantics document added 17–23 points. → Drafted descriptions are
  low-trust; the curated layer is the learned knowledge.

## 3. Learning from feedback and trust models

- **Snowflake Cortex Analyst** verified query repository: `verified_by`, `verified_at`; evaluation
  re-generates verified queries and compares results → `verified_by/at`, `export_confirmed`, revalidate.
- **Databricks Genie** trusted assets: parameterised examples are labelled *Trusted* when reused
  exactly; every answer asks "Is this correct?" (Yes / Fix it / Request review); behaviour "does not
  change based on user feedback alone" → the Yes/Fix it buttons, provenance badges, curator gate.
- **ThoughtSpot Spotter** coaching: users teach terms for themselves, privileged users share them, and
  personal corrections never override organisation definitions → personal-first scopes, the shared
  term winning on conflict.
- **Amazon Quick Sight** verified answers *(partly unverified)*: who verified, how long ago, usage →
  the knowledge page counters.
- **Continual learning from human feedback** (arXiv 2511.10674): question/SQL memory 34.1 → 47.0 on
  BIRD-dev; freely distilled feedback *hurt* a non-reasoning agent (77.4 → 64.5) → nothing is saved without
  explicit user acceptance.
- **DAIL-SQL** (arXiv 2308.15363): example selection by masked-question similarity, 82.0–82.4 vs 79.5
  random → roadmap item 1.
- **MIRA** (arXiv 2608.06950): check stored repairs against the DB before reuse, +16.5% on BIRD →
  revalidate on schema change.
- **Memory poisoning:** MINJA (arXiv 2503.03704) reached more than 95% injection success with only
  ordinary queries → personal isolation, 3 independent confirmations, curator promotion.
- **Memory libraries:** Mem0 2.2.1 (append-only, no verified-SQL notion), Letta (a whole runtime),
  Graphiti 0.31.2 (bi-temporal edges, needs a graph DB), LangMem 0.0.30 (stalled), Cognee 1.6.1, Vanna
  2.0.2 (**repo archived**). We borrowed Graphiti's close-don't-delete validity and none of the code.

## 4. Stack

| Component | Version (date) | License | Notes |
|---|---|---|---|
| Pydantic AI | 2.58.0 (2026-10-20) | MIT | OpenRouter + Anthropic providers, typed tool outputs, output validators, usage limits, prompt-cache settings, `instrument_all` |
| pydantic-evals | 2.58.0 | MIT | Dataset/Case/Evaluator |
| sqlglot | 30.24.0 (2026-10-20) | MIT | `qualify(validate_qualify_columns=True)` |
| SQLAlchemy | 2.1.5 | MIT | Introspection, pooling |
| PyMySQL | 1.2.3 | MIT | (mysql-connector-python is GPLv2: avoided) |
| fastembed | 0.9.0 (2026-10-07) | Apache-2.0 | `snowflake-arctic-embed-s` 384-d, 0.13 GB, NDCG@10 51.98 |
| NiceGUI | 3.18.0 (2026-10-07) | MIT | Chainlit's repo was **archived 2026-10-15** |
| FastMCP | 4.1.2 (2026-10-20) | Apache-2.0 | MCP spec 2026-07-28 |
| Faker | 40.43.0 | MIT | Synthetic values |
| uv | 0.11.33 locally (0.13.4 is current) | MIT/Apache | lockfile |
| MySQL | 8.0.44 | GPL (server) | Matches staging (`manifest.json`) |

Models on OpenRouter (live models API, 2026-10-21): `anthropic/claude-sonnet-5.5` $2/$10 per M tokens,
`anthropic/claude-haiku-5.5` $0.10/$0.50, `anthropic/claude-opus-5.5` $4/$20; all 1M context; no
`temperature`/`top_p`/`top_k` listed as supported parameters.

**Rejected:** OpenAI Agents SDK (non-OpenAI models are "best-effort, beta"; tracing defaults to OpenAI),
LangGraph (heavier; its SQL-agent tutorial says "not intended to be secure or for production use"),
Claude Agent SDK (drives the Claude Code CLI with a full toolset), DuckDB VSS (experimental, HNSW
persistence can corrupt), Qdrant local mode (dev/test only), SDV (BUSL-1.1; schema-only generation
is Enterprise-only), Snowfakery (archived), Synth (dormant), Gretel (acquired; library archived),
Atlas (views/triggers/routines are Pro-only), Chainlit (archived).

## 5. Primary sources

spider2-sql.github.io · bird-bench.github.io · bird-interact.github.io · livesqlbench.ai ·
arxiv.org/abs/2505.19988 · arxiv.org/pdf/2606.05836 · arxiv.org/abs/2511.17190 · arxiv.org/abs/2410.01943 ·
arxiv.org/abs/2508.15276 · arxiv.org/abs/2507.06467 · arxiv.org/html/2308.15363v4 · arxiv.org/html/2511.10674 ·
arxiv.org/abs/2608.06950 · arxiv.org/html/2503.03704v4 · arxiv.org/abs/2604.25149 ·
vldb.org/cidrdb/papers/2026/p5-jin.pdf · claude.com/blog/how-anthropic-enables-self-service-data-analytics-with-claude ·
docs.snowflake.com (verified query repository, Cortex Analyst evaluations) · docs.databricks.com/aws/en/genie/trusted-assets ·
docs.thoughtspot.com (Spotter coaching) · github.com/Kaelio/ktx · github.com/getzep/graphiti · github.com/vanna-ai/vanna ·
pydantic.dev/docs/ai · ai.pydantic.dev/models/openrouter · openrouter.ai/api/v1/models · modelcontextprotocol.io/specification/latest ·
qdrant.github.io/fastembed · github.com/Chainlit/chainlit · docs.sdv.dev · github.com/NVIDIA-NeMo/DataDesigner · atlasgo.io/features
