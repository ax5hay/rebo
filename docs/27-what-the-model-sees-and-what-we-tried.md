# 27 · What the model sees, and what we tried that did not make it (2026-10-21)

Two questions this page answers: *are we sending the model only what it needs?* and *what was tried,
measured and left out, and why?* Every number cites a results file or a doc section.

## 1. What goes to the model on one new question

ReBo is **retrieval-augmented, but agentic**: the database is never dumped into the prompt. The model
starts with a small, mostly cached prefix plus the items retrieval picked for this question, and then
looks up what it still needs with tools.

| Part | Size (JMS, 207 tables) | Cached across questions | Built by |
|---|---|---|---|
| Instructions (how to answer, safety, when to ask) | ~0.7k tokens | yes | `agent.INSTRUCTIONS` |
| Table names with row counts (no columns) | ~1.1k | yes (changes only on bootstrap) | `database_context` |
| Tool definitions (7 tools) | ~0.3k | yes | `build_agent` |
| Per-question context: learned knowledge (top 6), likely tables (top 8, one line each), stored values that match words in the question (top 8) | ~0.7k | no | `App._context_block`, hybrid retrieval |
| **First request total** | **~2.9k** | ~2.2k of it | |

Then the agent calls tools: `search_schema`, `describe_table` (one line per column since B-054,
value lists cut to 5), `search_values`, `find_join_path`, `search_knowledge`, `run_sql` (at most 20
rows back). **Each request re-sends the conversation so far**, which is how agent loops work with any
provider. That is where the "80k" comes from:

| Measured on the last 60 turns (`data/state.db`, turn.usage) | JMS | Demo (9 tables) |
|---|---|---|
| Median input tokens per question, all requests summed | 82k | 15k |
| Median requests per question | 5 | 3 |
| Average input per request | ~16k | ~5k |
| Share read from cache (10 % of the price) | 57 % | 65 % |

So no single request carries 80k tokens; five requests carrying the growing turn add up to it, and
most of the repeated part is billed at the cache price since B-052 (JMS $2.68 → $1.22 for 18
questions, doc 20). B-054 cut the tool results by 25 %.

**The RAG part (doc 08).** Three indexes, built at `rebo bootstrap` from the database alone:
schema (tables and columns with profiled descriptions), values (categorical values that are actually
stored, with counts) and learned knowledge (confirmed reports, terms, rules, joins people taught).
Each is searched with keyword ranking (SQLite FTS5 / Postgres full text, BM25) and dense vectors
(`snowflake-arctic-embed-s`, local ONNX, 384-d), fused with Reciprocal Rank Fusion. The vector store
is in-process (a numpy matrix per index) on SQLite and **pgvector** on Postgres. Retrieval feeds the
first request (above) and answers the agent's search tools. Saved reports matched by retrieval are
answered without any model when the question is the same (route "direct"/"cache") or only values
differ (route "params", one small call).

## 2. Routes that cost nothing or almost nothing

| Route | Model calls | When |
|---|---|---|
| direct / cache | 0 | the same question as a saved report or an earlier answer of yours |
| params | 1 small call | a trusted saved report with new values |
| rerun, drill, schedule | 0 | re-run a report, the rows behind a number, a scheduled report |
| **refine (B-060, new)** | **0** | switch a value filter under "Read as" (e.g. *open* → *everything but closed*) |

In production most traffic repeats, so these routes, not the model price, decide most of the bill.

## 3. Tried, measured, and not adopted

| Idea | What we measured | Verdict and why | File |
|---|---|---|---|
| Cross-encoder rerank of retrieval (B-051) | recall@5 of gold tables fell on both sets | rejected: the rerankers were trained on web text, not schema | doc 08 "Cross-encoder rerank" |
| Larger embedding models (embeddinggemma-300m, Qwen3-Embedding-0.6B) | recall@5 0.552 and 0.517 vs arctic-embed-s 0.621 | kept the small one: better and 5× faster | `jms_staging/embed_compare_2026-10-21.json` |
| Execution agreement: 2 extra candidate queries, judge on disagreement (B-048) | 10/12 + 10/12 on vs 10/12 + 9/12 off, +$0.0007 per checked turn | built, **off**: no clear gain at 12 cases | doc 04, `demo_property/eval_results_sonnet_agreement_on_{1,2}.json` |
| Retrieval by query shape (skeleton similarity, B-050) | finds the right saved report 13/17 vs words 1/17; answers 3/17 vs 3/18 at +22 % cost | built, **off**: strong retrieval signal, no answer gain yet (needs more saved reports) | `jms_staging/eval_results_shape_on_drafts20.json` |
| Spelling fallback for values (B-047) | no change on Sonnet | kept (free, helps cheaper models), not counted as a gain | doc 08 |
| Joins learned from confirmed reports (B-055) | leave-one-out 128–133/145 vs today 134/145 | not wired: the catalogue already knows 92 % of joins, and the same tables join differently by meaning | doc 26 step 2 |
| Composing answers from verified parts (doc 26) | 42 % of JMS reports composable; filters recur 5/16 | parked: filters and measures need a larger confirmed history to test honestly | doc 26 step 1 |
| Haiku for everything | demo 7/12 at $0.017 | too many wrong reports | `demo_property/eval_results_haiku_only.json` |
| Haiku, redo on Sonnet when a check fires (B-053) | demo 8/12 at $0.106 | the checks catch 2 of Haiku's 5 errors | `demo_property/eval_results_haiku_doubt_cascade.json` |
| Explore cheaply, Sonnet always writes the answer from the findings | demo 8/12 at $0.243 | rejected: Sonnet anchored on the cheap draft (same misses as Haiku) and cost as much as Sonnet alone on a small schema | `demo_property/eval_results_decide.json` |
| Gemini 3.8 Flash as agent, untuned | JMS 3 reports, 10 errors (tool budget) | not default; profiles added (B-012) | `jms_staging/eval_results_gemini38flash.json` |
| Local model in LM Studio (gemma-4-e2b) | demo 1/10 | far too weak for agentic SQL at this size | doc 20 §4.1 |
| DeepSeek V4.1 Flash as agent | demo 8/12 at $0.020 | weaker than GPT-6 Luna Pro at the same price | `demo_property/eval_results_deepseek-v4.1-flash.json` |
| EXPLAIN cost gate (B-058) | not built | plan estimates are dialect-specific and unreliable; timeouts already bound runaway queries; cartesian joins are caught structurally | BACKLOG B-058 |
| Rerun Haiku's answer on Sonnet only on doubt, without the doubt signal of a clarification | see B-053 | superseded by the doubt-gated decide below | |

## 4. What replaced "Sonnet for everything" (2026-10-21)

See doc 20 §5b for the measurement. In short: a cheap agent model answers; the strong model is called
only when the cheap one is unsure (it wants to ask, or a check fired), and then it decides from the
cheap model's lookups instead of exploring again.
