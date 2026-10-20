# 14 · Extraction ledger: what came from the previous bots

Sources:
- **Orchestrator:** `backend/app/services/reports_orchestrator/`, removed in `a0517aa6`
  (2026-09-20). Read it with `git show a0517aa6^:<path>`.
- **Agent:** `backend/app/services/reports_agent/`, live on `main`.
- Supporting code: `backend/app/services/sql_bot/`, `backend/scripts/schema_harness/`, `backend/app/config/*.yaml`.

Rule applied: **take ideas and lessons, not code**, unless the code was already generic.
Nothing in `src/` imports or copies JMS-specific logic.

## Kept (as an idea, re-implemented generically)

| From | What | Became | Why |
|---|---|---|---|
| Orchestrator `orchestrator.py` (preview → confirm → execute) | A human gate on correctness | **Feedback after the run** (`Yes, this is right` / `No, fix it`) feeding the trust lifecycle | PO feedback #1 said no preview/confirm before running; confirming *after* still captures the human judgement and now teaches the bot |
| Orchestrator `query_spec.py` (QuerySpec contract) | A structured, inspectable statement of intent | Typed `Report` output (`title`, `sql`, `assumptions`, `used_knowledge`, `learnable`) validated by Pydantic | Same auditability, enforced by the framework instead of 480 lines of builders |
| Orchestrator validated 18-prompt fast path (JMS-6723) | Pre-approved answers served fast | Personal/verified **examples** + provenance badges; repeat question answered in 5 s with 0 tool calls (doc 17) | Fills itself from use instead of being hand-curated |
| Orchestrator `clarify_mode.py`, `ambiguity_detector.py` | Ask when ambiguous | `Clarify` outcome with 2–4 options; ambiguity evidence comes from the value index (e.g. several stored people named Andrew, with counts) | No hand-written tie rules |
| Orchestrator `voice.py` | Consistent user-facing phrasing | `messages.py` (every sentence, doc 06) | — |
| Orchestrator `requester_admin.py` (me/my scope) | "my cases" → the requester's admin id | The host passes `X-User-Id`; the agent is told the user's host id and uses it when a table stores it | Generic: works for any id column |
| Agent `kernel.py` preview grant (hash of session+SQL) | Only previewed SQL may execute | Unnecessary: the output validator executes exactly the SQL it accepts, once | Simpler, same guarantee |
| `sql_bot/executor.py` | `fetchmany(limit+1)` truncation detection; **never dedupe rows** (counts must match the saved report) | `TargetDB.run` does both | Lesson kept |
| `sql_bot/sql_validator.py` | Read-only enforcement | sqlglot syntax-tree guard + read-only session + DB user (doc 07) | Regex validators miss nested/obfuscated statements |
| Agent `critic.py` (regex post-checks: NOT NULL, admin filter, activity type) | Catch silently wrong SQL | Output validator (must execute) + one 0-row nudge + plain-language assumptions shown to the user | Generic; the user is the critic, and their correction is learned |
| Agent `entity_probe.py` (name REGEXP on admin/contact) | Resolve people's names to ids | The value index covers every short string column with ≤ 1,000 distinct values (staff and contact first names on JMS-sized tables); `search_values("Andrew")` lists every stored match with table, column and count. Higher-cardinality columns are reached with a `run_sql` `LIKE` probe | Addresses the "multiple Andrews" root cause from the memory notes: the lookup is not role-filtered, so ties are visible |
| Agent `session.py` / `turn_intent.py` | Multi-turn state, refinement | Pydantic AI message history (last 4 user turns) + correction prefix | Framework-native |
| Agent `trace_log.py`, `llm_usage.py` | Per-turn traces and token usage | `turn.trace`, `turn.usage`, optional OpenTelemetry | — |
| `schema_harness/connection.py` | SSM URL + VPN private-IP rewrite | Copied into `tools/snapshot/snapshot.py` | Already generic; needed to reach staging |
| Schema digest "llm_allowed=false" sensitive columns (`contact.social_security_number`, `ed_profile.encrypted_ssn`) | Never show secrets | Automatic protected-column detection (name + ciphertext pattern); both columns are caught on the local copy (doc 17) | No list to maintain |
| `global_rules` note that `user_form_answer.text_answer` is Fernet ciphertext | Ciphertext exposure | Ciphertext value detector (`gAAAA…`) | Generic |
| `jms_report_validated_prompt_corpus.yaml` (18 PO-validated prompts) | Acceptance questions | `fixtures/jms_staging/eval.jsonl` | Test data, not bot config |
| Staging-confirmed definitions (JMS-6723 notes: sperm donors in intake = `gc_case` type + stage + `active=1`, `gc_id → contact`, both-IPs pattern via `family`) | Ground truth | **Expected learning outcomes** in doc 17. The bot found the case-type/stage/active definition on its own in the first live run | Must be learned or discovered, never hard-coded |

## Dropped (and why)

| From | What | Why dropped |
|---|---|---|
| `sql_bot/intent_signals.py` | 33 regex intent detectors (`ip_case_join_semantic`, `portal_login_semantic`, …) | JMS-only control flow in code; replaced by retrieval + learning |
| Orchestrator `report_patterns.py`, `pattern_linter.py`, `jms_report_patterns.yaml` | Saved-report shape patterns and lint rules | Same |
| Orchestrator `query_verifier.py`, `intent_invariants.py`, `activity_type_sql.py` | Table-specific SQL checks | Same |
| Orchestrator `consensus.py` | Agreement among the model's own variants by DB fingerprint | Research (doc 16): multi-candidate selection pays only on low-confidence turns, at +32% tokens / +72% latency; listed as a roadmap option |
| Agent `jms_report_concepts.yaml` (700 concepts), `jms_report_schema_v2.yaml`, vocabulary YAMLs | Hand-curated domain layer | Replaced by profiling + learned knowledge; doc 15 describes an optional one-time import as personal/proposed items |
| Agent `loop.py:140-196` | JMS join and portal rules in the prompt | Domain knowledge in a prompt is config in disguise |
| Agent `filter_semantics.py` | Hard-coded `assigned_admin` targets per JMS table | Same |
| Agent `builder_translate.py` (vendored JMS Report Builder translator) | Make bot reports editable in the JMS Builder | Host-specific output. Belongs in a JMS adapter outside the bot (doc 10 §5) |
| Agent `base_table.py`, `presence.py`, `concept_draft.py` | Heuristic base-table locks, presence checks, concept drafting | The model chooses with tools; drafting is replaced by `--describe` |
| Both | Whole-schema digest in the prompt (≈57 KB) | Retrieval; only likely tables and on-demand `describe_table` |
