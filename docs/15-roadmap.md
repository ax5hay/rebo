# 15 · What is built, what is designed, what is next

This branch is a **slim but working** implementation. "Built" items are in `src/` and exercised by
tests or the live runs in doc 17.

## Built

| Area | State |
|---|---|
| Bootstrap: introspect, profile, protected detection, value index, inferred joins, LLM descriptions, local embeddings | Built; live on the JMS local copy |
| Agent loop: 6 tools, 3 typed outcomes, output validator, 0-row nudge, usage limits, prompt caching | Built; 18-prompt live eval |
| SQL guard + read-only session + timeout | Built; 17 offline tests (+1 read-only session test) |
| Knowledge: examples, terms, notes, joins; trust lifecycle; provenance; conflicts; undo; staleness | Built; 12 offline tests; live confirm/correct/teach |
| API (12 routes), dev UI (3 pages) | Built; routes and pages return 200/403 as specified (UI not visually inspected in this session; the browser extension was not connected) |
| MCP adapter | Built; not exercised with an MCP client in this session |
| Evals (pydantic-evals), tracing (OpenTelemetry) | Built; eval run live; tracing wired but not exercised against a collector |
| Snapshot + local DB + synthetic data | Built; run against staging and locally |
| Dockerfile / `docker compose --profile bot` | Written; **image build not completed** in this session (stopped by the host for low memory) |

## Designed, not built (in order of value)

1. **Question masking for example retrieval** (DAIL-SQL). Before searching `knowledge_fts`,
   replace words that hit `schema_fts`/`value_fts` with placeholders, so "surrogates in screening"
   and "donors in matching" retrieve the same example structure. In `Knowledge.search`, one extra
   pass over the query. Reported gain: 79.9 → 82.0 execution accuracy on Spider-dev.
2. **Low-confidence second opinion.** When the provenance is `new` and the model made more than
   N assumptions, run a reviewer pass (Haiku) that receives the question, SQL, assumptions and
   10 sample rows and returns `ok | concern`. Show the concern as an extra assumption. About +6
   points in Anthropic's internal data team report, at +32% tokens, so only on low-confidence turns.
3. **Parameterised examples (Genie "trusted assets").** Store literals of confirmed SQL as named
   parameters (`:stage`, `:since`) using sqlglot to find literals. Reuse becomes deterministic:
   fill parameters → run, no model call. Needs one extra field `params` on `knowledge`.
4. **Notifications.** Push `stale` and `promoted` events to owners (host webhook). Today they see
   them on *My knowledge*.
5. **Correlated synthetic data.** Generate column groups (e.g. `stage` × `case_type` × dates in
   order) with an LLM-written generator per table group, cached as code in `tools/synth/generators/`,
   following the NeMo Data Designer pattern (Apache-2.0, 0.9.5). Today's columns are independent (doc 12).
6. **Cost limit per turn.** `UsageLimits(cost_limit=…)` needs model prices; `genai-prices` is
   installed but OpenRouter Claude 5.x pricing was not verified there, so it was left out.
7. **Optional import of the old JMS YAML** (`jms_report_concepts.yaml`, vocabulary) as
   `proposed` items owned by `import`, so curators can accept the useful ones. Not done by default:
   the point is to prove learning without it.
8. **Postgres state backend** for multi-instance deployments: `tsvector` for FTS, pgvector for
   vectors, the same tables.
9. **Fine-tuning from verified pairs.** Export verified examples (`evals.export_confirmed`) as
   training data once there are a few hundred. Not before.
10. **JMS host adapter** (outside this folder): the proxy with identity headers, and "Save to
    Report Builder" using JMS's own `report_query.py` translator.

## Known gaps to keep in mind

- The guard's column validation is skipped (with a warning) for SQL constructs sqlglot cannot
  qualify; the database still validates them. No such case occurred in the live runs.
- Join inference needs a name hint. Purely value-based joins are left to exploration and teaching.
- Value index: string columns with average length ≤ 60 and ≤ 1,000 distinct values. Free text and
  high-cardinality columns are reached through `run_sql` probes.
- The dev UI trusts the URL for identity. It is for local testing only.
