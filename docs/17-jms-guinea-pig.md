# 17 · JMS as the guinea pig: measured results and test script

JMS is the test database, not a dependency. Everything JMS-specific is under
`fixtures/jms_staging/`. This page records what was measured on 2026-10-21 and how to repeat it.

## 1. Setup that was measured

| Item | Value |
|---|---|
| Structure | JMS staging snapshot 2026-10-20 (207 tables, 2,769 columns, 440 FKs) |
| Data | Synthetic: `synth.py --cap 3000 --seed 7` → 87,941 rows |
| Bot DB user | `reports_ro` (SELECT only) |
| Bootstrap | 207 tables profiled; 22 joins inferred (after the best-candidate-per-column fix); 23 protected columns; 37,226 values indexed; 207 tables + 2,566 columns described by Haiku 5.5 |
| Agent model | `anthropic/claude-sonnet-5.5` via OpenRouter |
| Knowledge at start | empty |

Protected columns detected with no configuration: `contact.social_security_number`,
`ed_profile.encrypted_ssn`, `medical_release_form.patient_last_4_ssn`, every `*.pass_hash`
(admin, contact_lead, provider, provider_user, third_party_user, user, user_np), and OAuth / CSRF /
webhook / sync tokens.

## 2. The 18 PO-validated prompts (`fixtures/jms_staging/eval.jsonl`)

Full outputs (SQL, assumptions, clarifying options, token usage): `fixtures/jms_staging/eval_results_2026-10-21.json`.

| Result | Count | Cases |
|---|---|---|
| Report, executed, non-empty | **12** | 01, 02, 04, 06, 09, 10, 11, 13, 14, 15, 16, 17 |
| Clarifying question | **6** | 03, 07, 08, 18 (prompt still contains a `[placeholder]`), 05 ("this journey" with no context), 12 ("incomplete campaign" is genuinely ambiguous) |
| Errors | **0** | — |

- Median 14.5 s per question, 6 tool calls, about 71k input / 1.2k output tokens (≈ $0.15 at list
  price before prompt-cache discounts).
- The clarification options were grounded in stored values: the real template names, marketing
  sources and campaign flow statuses.
- For comparison, the current JMS agent with its 79-table YAML digest scored 12 composed / 6
  clarify on the same 18 prompts against staging (JMS-6815 notes). This bot reached the same split
  with no YAML. The data differs (synthetic vs staging), so this compares behaviour, not row counts.

**Row counts are not graded** because the data is synthetic. To grade correctness, confirm the
right answers in the UI, then `export_confirmed` → `gold_sql` cases (doc 11 §2).

## 3. Learning, measured live

| Step | Result |
|---|---|
| alice asks validated-01 | New report, 13 s, 5 tool calls. SQL: `gc_case.case_type='surrogate' AND stage='screening' AND active=1` + current sub-stage from `custom_sub_stage`/`template_sub_stage` |
| alice confirms | "Thanks, saved. … This only tunes the bot for you; other people won't see the change unless a curator shares it." |
| alice asks again | **5 s, 0 tool calls**, badge "Same as a report you confirmed earlier" |
| bob asks the same | New report, 16 s, 6 tool calls (alice's knowledge is private) |
| carol: "sperm donors in intake" | 51 rows, including inactive cases (the assumption stated this) |
| carol: No, fix it → "first/last name from contact; 'in intake' only ever means active" | 48 rows; card: term "in intake" = `gc_case.stage='intake' AND gc_case.active=1` |
| carol: Remember | "Got it. I'll use "in intake" in your future questions. Only you are affected." |
| carol, new conversation: "egg donors in intake" | badge **Built from saved knowledge: "in intake"**; `case_type='donor' AND stage='intake' AND active=1` |

The definitions confirmed on staging in JMS-6723 (sperm donors in intake = `gc_case` with
`case_type='sperm_donor' AND stage='intake' AND active=1`; egg donor is `case_type='donor'`; current
stage is `gc_case.stage`, not `status.stage`; contact via `gc_case.gc_id`) were all reached either
by exploration alone or with one user correction. None of them is written anywhere in `src/`.

## 4. Teaching script for a pilot (copy into the chat)

Use this to exercise the full lifecycle with three testers and one curator:

1. **alice**: "Show me all active surrogates in Screening and list their current substage." → Yes.
2. **bob, carol**: the same question → Yes. Their SQL may be written differently. If it returns the same rows, the third distinct confirmation (alice, bob, carol) auto-proposes it (doc 05 §3.1).
3. **cora** (`?role=curator`): Review queue → **Share with everyone**.
4. **dan**: the same question → badge "Verified report · checked by cora on …".
5. **dan**: "Which IP cases are in matching right now? Include the names and emails for both IPs."
   If one IP is missing → No, fix it → "both intended parents come from family.ip_1_id and
   family.ip_2_id" → Remember (a join or note). Check that dan's next "IP cases with both parents"
   uses it and that alice's does not.
6. **dan**: Withdraw that item in My knowledge → Undo → it is back.
7. Schema drift drill: `docker compose exec db mysql -uroot -proot jms -e "ALTER TABLE custom_sub_stage RENAME COLUMN ordering TO position"`
   → `uv run rebo bootstrap` → step 1's item becomes **Paused** → rename the column back →
   bootstrap → it is restored automatically.
   *Measured 2026-10-21:* the first half ran live. Alice's example went `stale` with the note
   "schema changed: Unknown column: ordering". The column was renamed back, but the restoring bootstrap
   was stopped by the host (low memory). The next bootstrap completed and **restored the item to
   `active` automatically** (observed live). It is also covered by
   `tests/test_learning.py::test_schema_change_marks_stale_then_repairs`. The
   same run found and fixed a bug: a bootstrap without `--describe` used to wipe drafted descriptions.

## 5. Repeat the measurements

```bash
uv run rebo bootstrap --describe
uv run rebo eval fixtures/jms_staging/eval.jsonl
```

Live numbers depend on the model and the synthetic seed. Keep the seed at 7 for comparisons.
