# 21 · Direction audit: what was asked vs what is built (2026-10-21)

Each requirement is quoted or paraphrased from the requests in this work. Each row has a verdict and
the evidence (file, test or measurement). "Partial" means it works but the doc 18 plan item named
closes the gap.

| # | Requirement | Verdict | Evidence |
|---|---|---|---|
| 1 | Generic, usable beyond JMS; JMS "just happens to be" the test DB | **Met** | No JMS names in `src/` outside the optional `adapters/jms.py` (checked by grep; prompt example fixed in `f8672333`). Offline tests run on a 3-table SQLite "shop" DB. CI guard planned (P0.4). |
| 2 | Minimal config: "the 10ish things we provide it, not a semantic info dump" | **Met** | `rebo.yaml`: 11 top-level keys (database, models, lmstudio_url, state_dir, limits, allowed_tables, protected_columns, sharing, embeddings, auth, adapters); unknown keys rejected; no semantic keys exist (`settings.py`, `tests/test_settings.py`) |
| 3 | Learns from users in chat, no config dump; a confirmed report "hardens" without code | **Met** | Trust lifecycle (doc 05); live: repeat question 5 s / 0 tools after confirmation; correction → remembered term → used in a new conversation (doc 17 §3) |
| 4 | Personal vs everyone made explicit to the user ("this tunes the bot for you, not everyone") | **Met** | `messages.py` keys `confirm_saved_personal`, `teach_saved_personal`, `remember_scope_note`; tests assert the wording |
| 5 | Real retrieval and agentic loop, best current tech, not hand-written heuristics | **Met** | Pydantic AI tool loop; FTS5/BM25 + vectors + RRF; profiling-based metadata; sqlglot syntax tree. Remaining heuristics are generic (secret-name patterns, identifier splitting, the 60% overlap routing threshold) |
| 6 | Self-contained, zippable, separate repo on another PC | **Met** | `rebo/` needs nothing from the parent repo; `git subtree split` recipe (doc 18 §1); uv lockfile; compose for the DB |
| 7 | Complete snapshot of JMS staging, replicable locally, with synthetic data; aws-vault for RDS | **Met** (structure + statistics; **no rows by design**) | `fixtures/jms_staging/` (207 tables, 440 FKs); `docker compose up -d db`; `tools/synth` (87,941 rows) |
| 8 | No JMS RDS or APIs in the new repo; JMS APIs mocked | **Met** | `mocks/jms/server.py` (token, admins, custom-report save + Builder grammar, re-run); `adapters/jms.py`; 11 tests. Not yet mocked: SQS + WebSocket push (P2.5) |
| 9 | LM Studio for offline inference | **Met (wire-tested, not run against a real LM Studio)** | `lmstudio:` provider; full agent turn over the OpenAI-compatible protocol against a stand-in server (`test_lmstudio_wire_protocol_end_to_end`). LM Studio is not installed on this machine |
| 10 | Mainly proprietary APIs; Claude now, Gemini (latest) to experiment | **Partial** | `openrouter:`, `anthropic:`, `google:` providers. Claude Sonnet/Haiku 5.5 measured live and working. Gemini 3.8 Flash measured live through OpenRouter: **3 reports / 5 clarify / 10 errors**, mostly the tool budget (doc 20 §5). Per-model tuning is P1.10. Direct `google:` builds offline (no Gemini key here) |
| 11 | Fewest turns: clarify and drill down efficiently | **Partial** | One-turn bundled clarifications (≤ 3 questions) and follow-up chips (`eeb9ba64`); 6 of 18 prompts clarified, all justified. Gaps: deterministic ask-gate (P1.2), per-user memory of clarification answers (P1.3), multi-turn eval (P1.9) |
| 12 | Cost efficient | **Partial** | Routing: reuse → fast model, new → agent, failure → escalate (`0bd04df1`, `c0f10b3e`). Measured: Sonnet $2.02 vs Haiku cascade $0.36 for 18 questions. Gaps: no-LLM parameterised reuse (P1.5), stable cache prefix (P1.8) |
| 13 | Accurate, minimal error margin | **Partial** | 0 errors in every live run; every report executed before being shown; assumptions shown. But **no gold answers yet**, so accuracy is not measured, and run-to-run variance exists (doc 20 §5). Gaps: P1.1 gold set, P1.2/P1.4/P1.7 checks |
| 14 | Small commits so every change is tracked | **Met** | One commit per change on `feat/rebo-standalone` (list in doc 18 §3), each with its test; rules and plan in doc 18 |
| 15 | Nothing on the remote; rest of the repo unaffected | **Met** | Branch has no upstream; only `rebo/` changed |
| 16 | Extremely detailed docs, down to code and the exact user-facing sentences | **Met** | docs 01–21 |

## Added 2026-10-21 (second request)

| # | Requirement | Verdict | Evidence |
|---|---|---|---|
| 17 | Open-source suggestions are suggestions; the agent researches for itself | **Met** | `AGENTS.md` §4 research protocol; banners on docs 19 and 20; doc 18 §0 |
| 18 | Everything needed from JMS is inside the zip; nothing JMS is reachable afterwards | **Met** | doc 23 §2 inventory: structure, profile, contract schemas, JWT/WS/Builder rules, 18 prompts, 79 gold reports, mock JMS, adapter; `tools/export_bundle.py` with secret/host checks |
| 19 | Replicate the DB and run everything locally | **Met** | Docker MySQL 8.0.44 + synthetic rows; bot, mocks and evals run with no JMS |
| 20 | A made-up similar setup with different data, only the config changed | **Met** | `fixtures/demo_property/` (builder, 5-line YAML, 10 gold); live 7/10 content match, 9/10 row counts |
| 21 | Config stays ~10–20 lines; people may edit it by hand | **Met** | `rebo.example.yaml`; `rebo config check`; owner API/UI with validation, audit and rollback |
| 22 | Only higher admins change config | **Met** | role `owner`; `admin.save_config` raises for others; `test_only_owners_touch_configuration` |
| 23 | Normal admins add and edit what the bot learned (memories) | **Met** | `add_knowledge` / `edit_knowledge`; export/import YAML; `test_editing.py`, `test_admin.py` |
| 24 | Users request fixes they can't make | **Met** | `create_request` routed to admins or owners; resolve with a note; `test_requests_route_to_the_right_people` |
| 25 | Feedback can be reverted and given in full words | **Met** | `undo_feedback` (reverses exactly what it did); notes stored and run as the correction; tests |
| 26 | More user aids | **Partial** | 12 aids live (doc 22 §2); 14 more specified as one commit each (doc 22 §3, doc 18 P1.11+) |
| 27 | Accurate with minimal error margin, measured | **Partial** | Demo domain 7/10 content and 9/10 row-count match. The JMS gold needs PO-written questions before it can measure anything (doc 18 P1.1) |

## Deviations to be aware of

- **Snapshot without rows.** You asked for a "complete snapshot". I captured the complete structure
  plus statistics and filtered categorical values, and generated synthetic rows instead of copying
  data, because the snapshot is meant to leave AWS and travel in a zip. Value lists were filtered for
  personal data (doc 12 §1).
- **Default model.** Sonnet 5.5 stays the default agent model. The Haiku-first cascade costs 5.7×
  less but made a grain error the validator cannot catch (doc 20 §5). It is a one-line config switch.
- **Builder-editable output** (the JMS-6757 constraint) is not enforced in the core. It is planned
  as an adapter-level output profile (doc 18 P4.1), so the product stays generic.
