# HANDOFF: state of the work (update at the end of every working session)

Last updated: 2026-10-21, at the end of the build on the original machine (branch
`feat/reports-bot-standalone` in orchid-ai-intake-bot, folder `reports-bot/`). Everything here is
also in git history; this file is the short version a new session reads first.

## 1. Where things stand

- **Working product: ReBo** (renamed from reportsbot on 2026-10-21; package `rebo`, CLI `rebo`,
  `REBO_*` env, `rebo.yaml`). Private repo **github.com/ax5hay/rebo**, CI green (SQLite, Postgres +
  pgvector, web + Playwright, dependency audit), Dependabot weekly.
- **Product UI** in `web/` (React; Ask, What I taught, Review, Admin, Insights, Configuration), served
  at `/` by `rebo serve` when built; second design (sidebar, ⌘K palette, calm answer panels, plain
  query steps from the syntax tree, dark mode). NiceGUI pages only with `--nicegui`.
- **Observability on by default**: Phoenix traces (one trace per question), people's feedback and eval
  verdicts as trace annotations, Insights page with live health checks, accuracy history, cost.
- Everything from B-001…B-044 (not B-015/B-041, which need a person; B-045 blocked on the Gemini
  free tier). 164 offline tests; 268 with Postgres.
- **Measured with keys (2026-10-21b):** JMS 18 prompts Sonnet 13 reports / 5 clarify / 0 errors $2.68;
  Haiku cascade $0.14; Gemini with profile 13 reports, 2 errors (504s); demo gold 8/10; conversations
  4/5; repeat question $0, new value $0.00013 (B-008); Gemini free tier: 3.5-flash-lite 7/10 at $0
  (3.8-flash's free quota is 20 requests/day). Still unmeasured: B-009 and B-019 effects.
- **Next work:** `BACKLOG.md`. Left after the second machine: B-043 (visual check), B-044 (LM Studio,
  in progress), B-045 (needs a Gemini key), B-015 and B-041 (need a person), and every
  `eval pending: needs llm` measurement (B-005, 006, 008–013, 019, 042; each names its results file).
  `tools/doctor.py` prints the next doable item.
- **2026-10-21c (third pass):** README/OPERATIONS/SECURITY in the maintainer's house style (banner,
  screenshots, mermaid diagrams), repo description and topics set; Markdown rendered on every text
  surface (`web/src/md.tsx`); palette v3 "ledger" (ink rail); CodeMirror editors for YAML/SQL and
  highlighted queries; Table/Chart toggle; Docker image now ships the web app; research pass recorded
  in doc 16 §5 with B-046…B-051 (046 SQL traps and 047 spelling fallback done; 048–051 open).
  Evals now ask as a new person per run (the answer cache had been replaying repeat runs).
  Measured after: B-047 spelling fallback no gain on Sonnet (kept, free); B-051 rerankers rejected
  (recall@5 fell on both sets); B-049 back-translation adopted (false alarms 3 → 0/1, recall unsteady).
  Open: B-048 (candidates + execution agreement, needs llm, behind a flag) and B-050 (skeleton similarity).
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
| SQL-trap checks (B-046), demo gold, Sonnet | 8/10 → 8/10, $0.236 → $0.242, no trap fired | `fixtures/demo_property/eval_results_sonnet_traps.json` |
| Embedding models on the JMS catalogue (12 validated questions, recall@5 of gold tables, hybrid) | arctic-embed-s 0.621 (kept), embeddinggemma-300m 0.552, Qwen3-Embedding-0.6B 0.517 | `fixtures/jms_staging/embed_compare_2026-10-21.json`, doc 08 §4b |
| Synthetic data date order | 9,809 violations → 0 with the derived spec | doc 12 §3 |
| genai-prices vs OpenRouter list prices (2026-10-21) | Sonnet 5.5 equal; Haiku 5.5 5× high; Gemini 3.8 Flash 9% low (cost cap scaled) | doc 20 §2.2 |

Run-to-run variance is real (one prompt gave 55 rows in one run and 5 in another). Compare changes
on gold answers, not on row counts of unconfirmed answers.

## 3. Gotchas (each cost time once)

- A `REBO_DATABASE_URL` in `.env` overrides `database:` in every YAML. Keep `.env` for API
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
- On macOS the copied tree had CRLF line endings on some files: `git status` showed them modified with
  no content change (`git diff --ignore-cr-at-eol` empty). They were stashed, not committed.
- Postgres tests: `docker compose up -d state-db` then
  `REBO_TEST_STATE_URL=postgresql://rebo:rebo@127.0.0.1:5433/rebo uv run pytest`.
- Web tests: `cd web && npm ci && npm run build && npx playwright test` (starts `tests/web_server.py`).
- Chain shell commands with `set -o pipefail` before `pytest | tail`: a failing test once slipped into
  a commit because the pipeline's exit code was tail's.
- The Gemini free tier allows 5 requests/minute and 20/day per model; one ReBo turn needs about 10.
- `fastembed` 0.9.0 caps Pillow < 13; `[tool.uv] override-dependencies` lifts it for the security fixes.
- In Chrome 156 `scrollIntoView` returns a Promise: never return it from a React effect.
- The domain-word guard (`tests/test_no_domain_words.py`) flags plain words that are also JMS table
  names (template, family, ...). Add genuine English words to `PLAIN_WORDS`; never JMS identifiers.
- The exact answer cache is per asker and model: any A/B or repeat run must ask as a fresh person
  (`evals.fresh_eval_user`, the default since 2026-10-21c), or the second run is replayed at $0.
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
| 2026-10-21 | original machine | everything up to the "continue" protocol; a fresh-machine simulation (unzip → `uv sync` → doctor) found and fixed two bugs: the demo config was never shipped, and keys in `.env` were invisible to the bot. Verified: history restored, 81 tests pass, NEXT = B-001 | B-001 |
| 2026-10-21 | second machine (macOS) | installed uv (brew); CRLF noise stashed; B-001…B-044 done in small commits; keys arrived: pending measurements run; renamed to ReBo; private GitHub repo; full product UI in React; observability by default (Phoenix traces, annotations, Insights); pgvector; PatientModel for rate limits; Pillow 13 security override; fixed: conversation access by others, X-User-* spoofing behind the proxy | Gemini free-tier staggered runs; B-008/009/019 measurements; B-015/041 need a person |
| 2026-10-21 | third pass (macOS) | house-style README/OPERATIONS/SECURITY, repo topics; Markdown on every surface; palette v3; CodeMirror editors; Table/Chart; Docker image ships the UI; research pass (doc 16 §5): B-046 SQL traps, B-047 spelling fallback, B-049 back-translation adopted, B-051 rerank rejected; eval cache-replay bug fixed | B-048, B-050 |
