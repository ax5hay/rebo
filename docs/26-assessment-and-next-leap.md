# 26 · Where ReBo stands, and the next leap (2026-10-21)

## 1. How far the bot is built (architecture and implementation, models aside)

Scored against a production v1 of a self-learning reports bot, by what exists and was verified here.

| Area | State | Score |
|---|---|---|
| Answer loop: routes (saved, cache, params, reuse, new, rerun, drill), agent tools, clarification, follow-ups | complete, measured | 90 % |
| SQL safety: syntax-tree guard, read-only session and user, timeouts, protected columns, trap checks | complete; no EXPLAIN cost gate, no row-level security passthrough | 80 % |
| Learning: personal first, shared by evidence, history and undo, stale detection, defaults, requests | complete | 90 % |
| Retrieval: full text + vectors, RRF, value index, masking, spelling fallback | complete; several alternatives measured and rejected | 85 % |
| Verification: grain, traps, second opinion with back-translation, agreement and shape checks (off) | broad; precision/recall measured only on 10–20 cases | 70 % |
| Cost: saved/cached repeats at $0, cascade switch, rate and cost caps | message-history caching was missing (fixed 2026-10-21, being measured) | 60 % |
| Observability and evals: Phoenix traces, annotations, Insights, eval runner, results files | good tooling; **gold sets are tiny** (12 demo, 18 JMS, drafts unvalidated) | 55 % |
| Product UI: Liquid Glass, every page, roles, help, preferences; Chromium + WebKit tested, Firefox in CI | complete | 90 % |
| Production: Docker image, compose with Postgres + pgvector, login proxy, migrations, runbook | complete; not load-tested, no multi-tenant isolation | 65 % |

Overall: about **75 %** of a production v1. What is missing is mostly **evidence** (validated gold
sets and real users), **row-level security**, **cost efficiency** and **scale testing**, not features.

## 2. What the research says (2025–2026), ranked for ReBo

Sources and verification marks are in the research notes; the eight changes, in order:

1. **Cache the growing turn**, not only instructions and tools (done 2026-10-21; measured in doc 20).
   On JMS, 83 % of input tokens were uncached; each turn re-sent its tool results 4–5 times.
2. **Verifier-gated cascade**: Haiku by default, Sonnet only when a check fires (trap, grain, second
   opinion, disagreement, clarification). Own data: $0.14 vs $2.68 for 18 questions.
3. **Smaller tool results**: per-tool token budgets; `describe_table` returns only relevant columns.
   About 80k input tokens per JMS question today.
4. **Learned semantic fragments** from confirmed reports (Snowflake's verified-query optimization
   does a curated version; "Beyond the Harness", arXiv 2608.22830: usage-derived context +12–25 %).
5. **Clarify only the part that disagrees**, as multiple choice built from the syntax-tree diff
   (AmbiSQL, arXiv 2508.15276; BIRD-Interact).
6. **Metamorphic checks on synthetic data** (SQLHD, arXiv 2512.22250: 69–83 % F1 without gold).
7. **EXPLAIN gate and row-level security passthrough** (GROUND, arXiv 2608.26157; CYGNET).
8. **Confirmed reports as a nightly regression suite** (Databricks Genie benchmarks; LinkedIn SQL Bot).

## 3. The leap: a verified query algebra that ReBo learns from use

**Observation.** On enterprise databases the limit is knowledge, not the model: BEAVER's best agents
reach 10.8 %, and 30.1 % when given the sub-steps; usage-derived context adds 12–25 %. ReBo already
collects the best knowledge there is (reports that people confirmed), but stores it as whole reports.
A confirmed report helps only questions that look like it. Our own B-050 measurement shows the
structure is there: the shape of a draft finds the right saved report 13/17 times where the words
find it 1/17.

**Idea.** Break every confirmed report, with sqlglot, into its parts and keep the parts, not only the
report:

| Part | Example | From |
|---|---|---|
| entity and grain | one row per customer | FROM, primary keys, GROUP BY |
| filter | "paused" = `status = 'paused'` | WHERE, with the user's words that led to it |
| measure | order value = `SUM(orders.amount)` | aggregates, with their join path |
| dimension | per month = `substr(placed_at, 1, 7)` | GROUP BY expressions |
| join path | orders → customer on `customer_id` | ON clauses |

Each part is content-addressed (canonical syntax tree), so the same filter in twenty reports is one
part with twenty confirmations from however many people. Trust attaches to parts: a part confirmed
by three people inside different reports is verified **without anyone reviewing it as a part**.
This is the existing "shared by evidence" rule, applied at a finer grain.

**Answering.** A new question becomes a plan over parts: choose an entity, filters, measures and
dimensions, then **compile** the SQL deterministically from verified parts. Only the gaps (a filter
nobody has confirmed yet) go to the agent, and only for that piece. Then:

- **Accuracy.** Coverage grows combinatorially: confirming "paused customers" and "order value per
  month" answers "order value of paused customers per month" from verified parts, never seen whole.
- **Cost.** A fully covered question needs one cheap planning call or none (slot filling over parts),
  instead of 4–5 Sonnet requests at about 80k tokens. Partly covered questions send the agent only
  the gap.
- **Trust you can scan.** The answer shows each part with its own label: *paused customers: verified
  (12 confirmations) × order value: verified × per building: new, check this*. People check one
  part, not a whole query.
- **Feedback that propagates.** "Exclude test accounts" corrects the *filter*; every report and future
  answer that uses it is fixed at once, with the history and undo ReBo already has.
- **Proof before promotion.** A new part is tested before it is shared: run on the synthetic shadow
  database (`tools/synth`) with metamorphic mutations (duplicate child rows, inject NULLs, shift
  dates) and check the invariants its grain implies. Parts that fail are not promoted.

**Novelty, as far as the research found.** Verified-query repositories (Snowflake VQR) store whole
queries, curated by admins; step-wise verification (Reward-SQL) works inside one query; semantic layers
are configured by people. No published system **learns** a library of SQL parts from end users'
confirmations, weights trust per part by independent evidence, composes answers from verified parts
with per-part provenance, and proves new parts metamorphically before sharing them. It also keeps
ReBo's first rule: nothing is configured; the "semantic layer" emerges from use and remains ordinary,
undoable learned knowledge.

**How to know it works (before building all of it).**
1. Offline, no model: decompose the 77 JMS gold reports and the 12 demo reports; measure how many
   parts recur across reports and how many gold reports are fully coverable from parts of the
   *other* reports (leave-one-out coverage). If coverage is low, stop.
2. A compositional split: confirm reports A and C, ask B whose parts come from A and C; compare
   correctness, tool calls and cost with and without compiled parts (`tools/eval_run.py`).
3. Metamorphic proofs: mutate gold SQL into known-wrong variants; measure how many the shadow-database
   invariants catch and how many correct parts they wrongly reject.

**Step 1 done (2026-10-21, `tools/parts_coverage.py`, no model):**

| Set | Parts covered by other reports (exact / values changed) | Reports fully composable (values changed) | By kind (covered/all) |
|---|---|---|---|
| JMS, 72 human-built reports | 64 % / 69 % | **30/72 (42 %)** | entity 63/72, join 93/144, filter 5/16 |
| Demo, 12 deliberately varied reports | 61 % / 61 % | 1/12 | entity 10/12, join 16/18, filter 4/18, measure 2/4, dimension 2/4 |

Joins and entities, the knowledge enterprise benchmarks name as the bottleneck, recur heavily;
filters are what make a question specific. So the first build is a **learned join-and-entity library**
(verified join paths and base entities composed deterministically) with the agent writing only the
filters, and full composition where coverage allows (42 % of the JMS reports). Files:
`fixtures/jms_staging/parts_coverage_2026-10-21.json`, `fixtures/demo_property/parts_coverage_2026-10-21.json`.

Backlog: B-052 (caching measurement), B-053 (cascade), B-054 (tool budgets), B-055 (part library,
offline coverage first), B-056 (part-level clarification), B-057 (metamorphic proofs), B-058
(EXPLAIN gate, RLS passthrough), B-059 (nightly regression from confirmed reports).

**Step 2 (2026-10-21, `tools/join_library_compare.py`, no model): joins learned from confirmed reports
do not beat the catalog.** Leaving each JMS report out, the bot's join paths reproduce its joins
134/145 today (declared + inferred at bootstrap); with the other reports' joins preferred, 128/145,
and 133/145 when only table pairs that every report joins the same way are trusted. Demo: 18/19 either
way. Two lessons: the catalog already knows the joins (92 %); and the same two tables are joined on
different columns depending on meaning, so "what another report did" is not a safe default. The join
library is kept as a function (`Knowledge.confirmed_joins`), **not wired into the agent**. The parts
idea stands or falls on filters and measures, which recur far less (filters 5/16 on JMS): it needs
a larger confirmed history than this repository has before it can be tested honestly. Found on the
way: `Catalog.join_path` crashed on equal-cost ties (fixed, test added).
