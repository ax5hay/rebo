# HANDOFF: state of the work (update at the end of every working session)

Last updated: 2026-10-21, at the end of the build on the original machine (branch
`feat/reports-bot-standalone` in orchid-ai-intake-bot, folder `reports-bot/`). Everything here is
also in git history; this file is the short version a new session reads first.

## 1. Where things stand

- **Working product, slim build.** Bot, learning lifecycle, roles (user/admin/owner), editable memory,
  undoable feedback, requests, owner config editing, JMS adapter + mock, demo domain, evals, export
  bundle, doctor. 80 offline tests passing.
- **Next work:** `BACKLOG.md`, in order, starting at the first `[ ]` item the machine can do
  (`tools/doctor.py` prints it). B-001 … B-045 cover every proposed item from docs 15, 18 and 22.
- **Direction and rules:** `AGENTS.md`. Plan and gates: `docs/18-production-build.md`.

## 2. Measured facts (do not re-derive; re-measure only when a change could affect them)

| What | Result | File |
|---|---|---|
| 18 PO prompts on the local JMS copy, Sonnet 5.5 | 12 reports, 6 justified clarifications, 0 errors, ~$0.11/question | `fixtures/jms_staging/eval_results_sonnet.json` |
| Same, Haiku → Sonnet escalation | 11 reports + 1 answer, 6 clarifications, 0 errors, $0.36 for 18 (5.7× cheaper); one fan-out grain error | `eval_results_haiku_cascade.json` |
| Same, Gemini 3.8 Flash via OpenRouter, untuned | 3 reports, 5 clarifications, **10 errors** (tool budget), median 92 s | `eval_results_gemini38flash.json` |
| Made-up demo domain, Sonnet, empty knowledge | 7/10 content match, 9/10 row-count match, 1 justified clarification, $0.27 | `fixtures/demo_property/eval_results_sonnet.json` |
| JMS gold (79 human reports) | **not usable yet**: 67 prompts are "Show me <title>"; drafts are B-014, PO validation B-015 | `fixtures/jms_staging/eval_results_gold25_sonnet.json` |
| Learning loop | confirm → repeat question answered in 5 s with 0 tool calls; correction → remembered term reused in a new conversation | doc 17 §3 |
| Schema drift | renamed column → item stale → restored automatically after the fix | doc 17 §4 |

Run-to-run variance is real (one prompt gave 55 rows in one run and 5 in another). Compare changes
on gold answers, not on row counts of unconfirmed answers.

## 3. Gotchas (each cost time once)

- A `REPORTSBOT_DATABASE_URL` in `.env` overrides `database:` in every YAML. Keep `.env` for API
  keys only. Doctor warns about this.
- On Windows Git Bash, paths that start with `/` get rewritten. Prefix commands that pass such
  arguments with `MSYS_NO_PATHCONV=1`.
- Shell heredocs containing single quotes broke in the agent's shell wrapper. Write scripts to a file
  and run them instead.
- Pydantic AI 2.x: `result.usage` is a property; injected HTTP clients must be `httpx2`; Claude 5.5
  rejects `temperature`, so none is sent.
- sqlglot 30: `NOT LIKE` is `Like(negate=True)`, not `Not(Like)`.
- MySQL 8 `information_schema` returns upper-case column names unless aliased.
- SQLite/Postgres `TEXT` is the normal string type: decide "free text" by average length, not by type.
- When killing a process by command-line match, the pattern can match your own shell. Kill by port
  or PID instead.
- The host stopped long background jobs under memory pressure. Run heavy jobs (bootstrap with
  embeddings, Docker builds, synth) one at a time.

## 4. Decisions already made (do not reopen without new evidence)

- No domain configuration, ever. Meaning is learned from the database and from people (AGENTS.md §1).
- Sonnet stays the default agent; the Haiku cascade is a config switch (accuracy vs cost, doc 20 §5).
- Personal-first learning; shared only after 3 independent agreements plus an admin, or an admin directly.
- Accuracy metric: content, not presentation (`evals.columns_match`).
- The JMS Report Builder constraint is an adapter-level option (B-038), not core behaviour.
- The staging snapshot holds structure and statistics only, never rows. JMS is unreachable from now on.

## 5. Working style the user expects

- **Be precise.** Verify before stating; cite `file:line`; say "not verified" or "I don't know"
  rather than guess.
- **Be terse.** Answer first, minimal preamble; spend tokens on work, not narration.
- **Small commits.** One behaviour change each, with its test and doc change; commit messages say
  why and what was measured.
- **Don't push or publish** unless the user asks. Committing locally is expected.
- **Report outcomes faithfully.** Failed tests, skipped steps and stopped jobs are stated plainly.

## 6. Session log

| Date | Session | Done | Next |
|---|---|---|---|
| 2026-10-21 | original machine | everything up to `BACKLOG.md` creation (see git log) | B-001 |
