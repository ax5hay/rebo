# 01 · Overview

## What this is

**ReBo** (`rebo`) is a self-contained natural-language reports bot. Point it at any relational
database, and business users can ask for reports in plain words ("active clients in screening
with their sub-stage"). The bot explores the database, writes one read-only SQL query, runs it,
shows the rows, and says how it read the question. When the user says the answer is right, the
bot remembers it **for that user**. When enough people agree, or a curator approves, the knowledge
is **shared with everyone**. When the user says the answer is wrong, the bot fixes it in the same
chat and offers to remember the correction.

There are no YAML files describing the business domain, no hand-written concept registries, no
regex intent detectors and no per-customer code. Everything the bot knows about the database
comes from two sources:

1. **The database itself**, read once by `rebo bootstrap`: structure, statistics, the
   actual stored values of categorical columns, declared and inferred joins, and LLM-drafted
   descriptions (marked as drafts).
2. **People, in the chat**: confirmed reports, business terms, rules and joins, each with an
   owner, a scope and a trust state.

JMS is the first database it is tested on. Nothing in `src/` mentions JMS; the JMS-specific parts
live only in `fixtures/jms_staging/` (a structure snapshot, a statistics profile and the 18
PO-validated test prompts) and in this documentation.

## Goals

| Goal | How it is met |
|---|---|
| Works on any SQL database with no domain config | Introspection + profiling + value index + inferred joins (doc 03) |
| Learns from users without code changes | Knowledge store with a trust lifecycle (doc 05) |
| A user's teaching never silently changes other people's answers | Personal by default; sharing needs 3 independent confirmations to be *proposed* and a curator to *verify* (doc 05) |
| Cannot write, lock, stall or leak | Read-only DB user + syntax-tree guard + read-only session + timeout + protected-column detection (doc 07) |
| Honest about certainty | Every answer carries a provenance badge and plain-language assumptions (doc 06) |
| Survives schema changes | Table fingerprints; saved SQL re-checked and paused when it breaks (doc 05 §7) |
| Zippable, runs on another PC | One folder, `uv` lockfile, one SQLite state file, Docker Compose for the test DB (doc 13) |

## Non-goals (deliberately)

- **Writing data.** The bot never runs anything but `SELECT`.
- **Dashboards / charts.** It returns tables. A host app can chart them.
- **A hand-built semantic layer.** Research (doc 16) shows LLM-*generated* semantic layers are net
  negative unless people curate them. Here, people curate by confirming, which is what the
  knowledge store records.
- **Fine-tuning a model.** Learned memory takes effect immediately, can be inspected and undone,
  and costs nothing per customer. Confirmed pairs can feed fine-tuning later (doc 15).

## Principles that shape the code

1. **Ground truth over guesses.** The model must look things up (tables, columns, stored values,
   joins) with tools before using them. The guard rejects unknown tables and columns, and the
   output validator runs the final SQL before anyone sees it.
2. **Personal first, shared by evidence.** Learning is instant for the person who taught it,
   and slow and gated for everyone else.
3. **Never delete knowledge.** Items are closed (`retired`, `valid_to`) with an audit trail, so every
   change can be undone.
4. **Few, boring dependencies.** Pydantic AI (agent loop), sqlglot (SQL parsing), SQLAlchemy
   (database access), SQLite FTS5 (search), fastembed (optional local vectors), NiceGUI (dev UI).
5. **Safety limits are config; meaning is learned.** The only settings are wiring (URLs, keys) and
   limits (rows, timeouts, budgets). See doc 13 §1.

## How this differs from the two previous implementations

| | Orchestrator (`reports_orchestrator`, removed `a0517aa6`) | Agent (`backend/app/services/reports_agent`) | This bot |
|---|---|---|---|
| Control flow | Fixed stages: resolve → compose → probe → preview → confirm → execute | Tool loop, with much of the routing in Python heuristics | Tool loop (Pydantic AI); Python only validates |
| Domain knowledge | 33 regex intent detectors, pattern YAML, golden catalogs, verifier rules | 700-concept YAML registry, schema digest YAML, vocabulary YAML, JMS rules in the prompt | None at start; learned from the DB and from people |
| Retrieval | None (whole schema digest in the prompt) | Concept index over YAML | FTS5/BM25 + optional dense vectors, rank-fused; value index over stored values |
| Learning | None (hand edits) | None (hand edits) | Confirmations, corrections, terms, joins → trust lifecycle |
| SQL safety | Regex validator | Regex validator + preview grant | sqlglot syntax tree + column validation + read-only session + DB user |
| Output target | JMS Report Builder | JMS Report Builder (vendored translator) | Plain SQL + rows; a host adapter can translate (doc 15) |

What was carried over, and why, is listed item by item in doc 14.
