# BACKLOG: the ordered work list (read by the "continue" protocol in AGENTS.md §0)

Format, kept parseable by `tools/doctor.py`:

```
### [ ] B-NNN · Title           [ ] todo   [~] in progress   [x] done   [!] blocked (needs a human or a resource)
needs: offline | docker | llm | gemini | lmstudio | node | browser | human     (all must be available)
```

**Rules:**
- Take the **first** `[ ]` item whose `needs` are all available (doctor prints it), or resume a `[~]`.
- Follow its **do** steps, add tests, update the docs it names, and make small commits.
- Mark it `[x]` with the date and commit hashes on a `result:` line.
- `llm` means any LLM API key, used only to **measure**. If no key is available, implement and test
  offline, then add `eval pending: needs llm` to the result.
- Never start an item marked `human`. Leave it `[!]`.
- Doc references are in `docs/`. Background for every item: doc 18 (plan), doc 22 (aids).

---

## Phase P0: repository hygiene

### [x] B-001 · CI workflow
needs: offline
do: `.github/workflows/ci.yml` runs on push and PR: `uv sync --frozen --all-extras`, `uv run pytest -q`, `uvx ruff check src tests tools mocks --select F,E9,B --ignore E501,B008,B905`. No network beyond PyPI; no secrets.
done when: the workflow file exists, and running the same commands locally is green.
result: 2026-10-21, 3854d05 205d27c. Local: 81 passed, ruff clean (after fixing B017/F401). Not run on GitHub (not pushed).

### [x] B-002 · Pre-commit hooks
needs: offline
do: `.pre-commit-config.yaml` with ruff (same rules as B-001) and a local hook running `python tools/export_bundle.py --out <tmp>` in check mode. Add a `--check-only` flag to `export_bundle.py` that scans without writing a zip. Document in CONTRIBUTING (B-004).
done when: `uv run python tools/export_bundle.py --check-only` exits 0 on a clean tree and 1 when a fake key is planted (test).
result: 2026-10-21, see `git log --grep B-002`; 82 passed; pre-commit run --all-files passes. CONTRIBUTING mention left to B-004.

### [x] B-003 · Guard: no domain words in src/
needs: offline
do: `tests/test_no_domain_words.py`:
- Collect table names from `fixtures/*/profile.json` and the table names in `fixtures/demo_property/build.py`.
- Fail if any appears as a whole word in `src/rebo/**/*.py`, excluding `adapters/`.
done when: the test passes now and fails if `gc_case` is added to `agent.py`.
result: 2026-10-21, `git log --grep B-003`; verified both ways; 13 plain-English table names allow-listed in the test.

### [x] B-004 · CONTRIBUTING.md
needs: offline
do: Copy the commit rules (doc 18 §0), the research protocol (AGENTS.md §4), how to run the tests, evals and bundle, and the type prefixes. Link it from README.
done when: the file exists and is linked.
result: 2026-10-21, `git log --grep B-004`; also documents the B-002 pre-commit hook.

## Phase P1: accuracy, fewest turns, cost (product core)

### [x] B-005 · Grain check (fan-out warning)
needs: offline
why: Haiku returned one row per sub-stage instead of one per case (doc 20 §5). The validator can't see it, because the SQL runs.
do: In `agent.validate`, after a successful run:
1. Find the report's "entity key": the first projected column that is the PK of a FROM/JOIN table (sqlglot; `catalog` knows the PKs).
2. If `rows > distinct(entity key values)`, raise `ModelRetry` once: "rows repeat per <table>; one row per <entity> was probably intended: aggregate or pick one row".
3. If that is intended, the model re-presents with an assumption saying so.
done when:
- Offline tests (FunctionModel/MockTransport as in `tests/test_llm.py`): a fan-out report triggers exactly one retry, and a deliberate one-row-per-child report passes on the second attempt.
- doc 04 §7 updated.
result: 2026-10-21, `git log --grep B-005`; 94 passed. eval pending: needs llm (re-run the Haiku cascade set to see the fan-out case fixed).
eval 2026-10-21b: Haiku cascade validated-01 now 3 rows (= Sonnet; was 15), $0.14 for 18; not attributable to the grain check alone (data changed, retries not logged).

### [x] B-006 · Deterministic ask-gate
needs: offline
why: CIGAsk found that prompting alone over-asks or under-asks.
do: When the agent returns `Clarify`:
1. For each question, ask the model for the SQL of its first two options in the same run (new optional field `option_sql: list[str]` on `Question`). Or run a second short agent call with the fast model.
2. Execute each guarded SQL with `same_result`.
3. If every question's options return identical rows, convert the turn into a `Report`, using option 1 plus an assumption: "the readings X/Y give the same result".
4. Record `gate: asked|answered` in `turn.usage`.
done when:
- Offline tests cover both paths.
- `eval_run.py` reports the clarify rate.
- With `llm`, the 18 JMS prompts' clarify count is recorded in a results file.
- doc 04 §5 and doc 06 §6 updated.
result: 2026-10-21, `git log --grep B-006`; offline tests both paths; 98 passed. Implemented option 1 (option_sql in the same run). eval pending: needs llm (record the 18 JMS prompts' clarify count and gate_answered).
eval 2026-10-21b: Sonnet 18 prompts: 5 clarifications, gate asked 5 / answered 0.

### [x] B-007 · Remember clarification answers per user (aid)
needs: offline
do: When a user answers a clarification (the UI/adapter sends `Q → A`), store a personal `note` titled with the question, `body` = the answer, `source_turn` = that turn. No card: it applies only to that user. Visible and undoable in My knowledge. The prompt already gives personal notes to the model.
done when:
- Offline test: the same clarifying question is not asked twice. Use a FunctionModel that asks only when the note is absent from the context block.
- doc 22 §2 moves this from §3.
result: 2026-10-21, `git log --grep B-007`; 100 passed. Only answers matching an offered option are stored.

### [x] B-008 · Parameterised examples and no-LLM reuse; "Re-run with today's data" (aid)
needs: offline
do:
1. On confirm, extract the literals of the example's SQL with sqlglot into `params` (new JSON column, added via `store.MIGRATIONS`); keep `sql_template` with `:p1`… placeholders.
2. `_reuse_match` hit plus a question differing only in values: an `extract_params` call on the fast model fills the parameters. If the user's own example is an exact text match, run with no model call at all.
3. Add a "Re-run with today's data" button on past reports and `POST /api/turns/{id}/rerun`: same SQL, fresh rows, no model.
done when:
- Offline tests: an exact repeat makes 0 model requests; re-run returns fresh rows.
- docs 05 and 20 updated.
- `route: "direct"` appears in usage.
result: 2026-10-21, 4 commits (`git log --grep B-008`); 106 passed. Exact repeat of own question: 0 requests (route direct); value-only change: 1 fast request, 0 agent (route params); rerun: 0 requests. eval pending: needs llm (cost per repeat question). UI button not browser-tested.
eval 2026-10-21b: new $0.038 (3 requests); exact repeat after confirming $0 (0 requests, direct); new value $0.00013 (1 Haiku request, params) with the right filter.

### [x] B-009 · Question masking for example retrieval
needs: offline
do: In `Knowledge.search`, also search `knowledge_fts` with a masked query: words that hit `value_fts` or `schema_fts` are replaced by their table/column type token. Fuse both rankings (RRF).
done when: an offline test shows "paused customers" retrieves the example saved for "active customers". doc 08 §5 updated.
result: 2026-10-21, `git log --grep B-009`; 108 passed. Values masked, schema words not (they match literally). eval pending: needs llm.

### [x] B-010 · Stable cacheable prefix
needs: offline
do:
- Order the instructions as static text, then the table list (byte-identical across turns; sorted).
- Put the per-turn context block in the user message (already the case).
- Set `anthropic_cache_instructions='1h'`/tool definitions `'1h'` for `anthropic:` models.
- Log `cache_read_tokens` (already recorded).
done when:
- Offline test: two turns produce identical instruction text.
- With `llm`: a results file showing `cache_read_tokens > 0` on the second question.
result: 2026-10-21, `git log --grep B-010`; 109 passed. eval pending: needs llm (cache_read_tokens > 0 on the 2nd question).
eval 2026-10-21b: cache_read_tokens > 0 on every Sonnet turn (3k-27k).

### [x] B-011 · Multi-turn eval
needs: offline
do: `fixtures/*/conversations.jsonl`: scripted conversations of user turns, each with an expectation (report rows / clarify / follow-up chosen). Add `tools/eval_conversations.py`, which reports turns to the first correct report, clarify rate and cost.
done when: offline test with a FunctionModel; with `llm`, a results file for 5 demo conversations.
result: 2026-10-21, `git log --grep B-011`; 110 passed; 5 demo conversations written. eval pending: needs llm (results file for the 5 demo conversations).
eval 2026-10-21b: 4/5 conversations solved at turn 2, $0.19 (eval_conversations_sonnet.json).

### [x] B-012 · Per-model profiles; re-measure Gemini
needs: offline
why: Gemini 3.8 Flash gave 10/18 errors, mostly from running out of tool budget (doc 20 §5).
do: In `llm.py`, add a profile per model family:
- thinking level (`low` for Gemini 3.x),
- tool-call budget,
- `parallel_tool_calls`,
- output mode: ToolOutput, or PromptedOutput for LM Studio models that fail tool calls.
eval 2026-10-21b: eval_results_gemini_profile.json: 13 reports, 3 clarify, 2 errors (OpenRouter 504s; was 10 budget errors), median 104 s, $1.82.

Apply the profile in `App.ask` (UsageLimits) and in the model settings. **Research first** (AGENTS.md §4): current Gemini thinking parameters in Pydantic AI.
done when:
- Offline tests check that profiles are applied.
- With `llm` (OpenRouter is enough): `eval_results_gemini_profile.json` on the 18 prompts.
- doc 20 §5 updated with the numbers.
result: 2026-10-21, `git log --grep B-012`; 112 passed; research recorded in doc 20 §2.1. eval pending: needs llm (eval_results_gemini_profile.json on the 18 prompts, then doc 20 §5).

### [x] B-013 · Low-confidence second opinion
needs: offline
do: When provenance is `new` and there are more than 2 assumptions, run the fast model as a reviewer on question + SQL + assumptions + 10 rows. It returns `{ok: bool, concern: str}`; a concern is shown as an extra assumption marked "Check: …". Record `review: ok|concern` in usage.
done when: offline tests cover both outcomes; with `llm`, demo gold before/after in a results file.
result: 2026-10-21, `git log --grep B-013`; 115 passed. eval pending: needs llm (demo gold before/after).
eval 2026-10-21b: demo gold 8/10 (was 7/10); concerns 4, caught the 1 wrong report (precision 1/4).

### [x] B-014 · Draft real questions for the JMS gold reports
needs: offline
do: For each of the 67 `prompt_quality: title_only` rows in `fixtures/jms_staging/gold_custom_reports.jsonl`:
1. Read its `gold_sql`, `title` and `headers`.
2. Write the natural question a JMS admin would ask, into `draft_question` with `draft_by: agent`.
3. Leave `question` unchanged. **Do not** mark the drafts as gold.
done when: all 67 have `draft_question`; `tools/eval_run.py` gains `--use-drafts` to evaluate them, clearly labelled "draft questions, not PO-validated".
result: 2026-10-21, `git log --grep B-014`; 67/67 drafted (22 with draft_note on SQL/title mismatches); --use-drafts added. eval pending: needs llm. B-015 (PO validation) can now start.

### [!] B-015 · Product owner validates the JMS gold questions
needs: human
do: A PO reviews the `draft_question` values from B-014 and copies the accepted ones to `question` with `prompt_quality: question`.
done when: 30 or more validated questions exist; run the full gold eval with `llm`.

## Phase P1b: user aids (doc 22 §3), one commit each

### [x] B-016 · Favourites (pin a report)
needs: offline
do: `POST /api/turns/{id}/pin` stores a pinned report per user, as a personal example flagged `pinned` (new column via MIGRATIONS). Pinned reports appear first among the starters. Unpin is available.
done when: offline test; Ask page shows pinned reports; doc 22 updated.
result: 2026-10-21, `git log --grep B-016`; 117 passed. Ask page change not browser-tested.

### [x] B-017 · "What do you know about X?"
needs: offline
do: Add `GET /api/knowledge/about?q=` and a UI search box on My knowledge. It returns the visible knowledge items, matching tables/columns with their descriptions, and stored values (`search_values`), grouped and labelled by trust. Also add a chat path: the `Reply` outcome may cite items.
done when: offline test; doc 22 updated.
result: 2026-10-21, `git log --grep B-017`; 119 passed. UI not browser-tested.

### [x] B-018 · Explain this number (drill-through)
needs: offline
do: For an aggregated report, clicking a cell (UI) or calling `POST /api/turns/{id}/drill {row, column}` builds the detail query with sqlglot:
- remove the GROUP BY and aggregate,
- add the group values as filters,
- guard it and run it with no model.
done when: offline test on the demo DB (open maintenance per building → the rows for one building).
result: 2026-10-21, `git log --grep B-018`; 120 passed. UI row click not browser-tested.

### [x] B-019 · Personal defaults
needs: offline
do: Add a My knowledge section "My defaults" (date range, region, …) stored as personal notes titled `default: <name>`. The context block lists them first, and the prompt says to apply them unless the question says otherwise and to state them as assumptions.
done when: offline test with a FunctionModel checking the default reaches the prompt.
result: 2026-10-21, `git log --grep B-019`; 121 passed. eval pending: needs llm (prompt gained one instruction line).

### [x] B-020 · See as user X (admin)
needs: offline
do: Add `GET /api/admin/preview?user=X&q=…`, which returns the context block (visible knowledge) that user X would get. Admin only. Add a UI panel on the Admin page.
done when: offline test showing an admin sees X's personal items in the preview and a user gets 403.
result: 2026-10-21, `git log --grep B-020`; 122 passed. UI panel not browser-tested.

### [x] B-021 · Import diff preview (admin)
needs: offline
do: `admin.import_knowledge(dry_run=True)` returns the list of changes without applying them. The Admin page shows the diff before an Import button.
done when: offline test showing dry-run changes nothing.
result: 2026-10-21, `git log --grep B-021`; 123 passed. Dialog not browser-tested.

### [x] B-022 · Bulk review (admin)
needs: offline
do: Select several queue items, then Share or Reject them with one note. Add `POST /api/review/bulk`.
done when: offline test.
result: 2026-10-21, `git log --grep B-022`; 124 passed. UI not browser-tested.

### [x] B-023 · Usage dashboard (admin/owner)
needs: offline
do: Add an Admin page section and `GET /api/admin/stats`:
- confirmation rate per week,
- provenance mix,
- top questions,
- items most reported wrong,
- open requests by age,
- cost per day (`turn.usage` × price table from `tools/eval_run.py`; move PRICES to `llm.py`).
done when: offline test on seeded turns.
result: 2026-10-21, `git log --grep B-023`; 125 passed. UI not browser-tested.

### [x] B-024 · Config change preview (owner)
needs: offline
do: Before saving, `admin.save_config(preview=True)` validates and also:
- builds an App against the new config in a temp state dir,
- checks the database connects and the models parse,
- reports the differences.
No model calls.
done when: offline tests (bad database URL → readable error; good → OK).
result: 2026-10-21, `git log --grep B-024`; 126 passed. UI not browser-tested.

### [x] B-025 · Request notifications and ages
needs: offline
do:
- Optional `notify_url` key (one config line; webhook POST on request created/resolved and on item stale/promoted).
- Show request ages on the Admin page.
- Mock receiver in tests.
done when: offline test with an httpx mock; config doc updated (count stays ≤ 20 lines).
result: 2026-10-21, `git log --grep B-025`; 129 passed; config at 19 settings (test-enforced <= 20).

## Phase P2: production plumbing

### [x] B-026 · Postgres state backend
needs: docker
do: **Research first** (AGENTS.md §4; doc 19 §3 suggests Postgres 18 + pgvector + pg_textsearch). Then:
1. Add a `state_url` key (default: SQLite file).
2. Abstract `Store` SQL differences: FTS5 → tsvector or pg_textsearch, BLOB vectors → pgvector.
3. Run the whole test suite against both backends (pytest param; Postgres via docker compose service `state-db`).
done when: tests are green on both backends; doc 09 and doc 13 updated.
result: 2026-10-21, 3 commits (`git log --grep B-026`); 212 passed locally (130 SQLite + 82 Postgres 18.6). Built-in tsvector + BYTEA vectors (no extensions), decision in doc 19 §3. No state.db -> Postgres copy tool (knowledge moves via export/import).

### [x] B-027 · Schema migrations with Alembic
needs: offline
do: Replace `store.MIGRATIONS` with Alembic revisions (SQLite and Postgres). Keep the in-place upgrade path for existing `state.db` files.
done when: upgrading a copy of a pre-migration `state.db` works (test with a fixture DB).
result: 2026-10-21, `git log --grep B-027`; 131 passed (SQLite), 213 with Postgres 18.6; pre-migration fixture (schema of 9b81192^) upgrades in place.

### [x] B-028 · Better embeddings (optional TEI service)
needs: docker
do: **Research first.** Then:
1. Add an `embeddings_url` key to use a TEI container; otherwise keep fastembed.
2. Compare arctic-embed-s against EmbeddingGemma-300m and Qwen3-Embedding-0.6B on retrieval: hit@5 for schema search on the demo gold questions (new offline metric).
3. Switch the default only if better.
done when: a results table goes into doc 08, and the default is changed or kept with evidence.
result: 2026-10-21, `git log --grep B-028`; default kept (arctic hybrid recall@5 0.621 vs 0.552 / 0.517 on 12 validated questions), fixtures/jms_staging/embed_compare_2026-10-21.json. `embeddings` key takes a model or TEI URL (no new key). TEI not run (amd64-only image).

### [x] B-029 · Streaming (AG-UI)
needs: offline
do: **Research first** (Pydantic AI AG-UI adapter). Then add a `/api/agui` endpoint that streams tool progress and the final payload; the NiceGUI Ask page shows the progress.
done when: offline test with TestClient streaming and a FunctionModel.
result: 2026-10-21, `git log --grep B-029`; 134 passed. Also fixed: conversations could be continued by another user (separate fix commit). UI progress not browser-tested.

### [x] B-030 · Durable jobs, scheduled reports, mock JMS async push
needs: offline
do: **Research first** (DBOS). Then:
1. Long turns and scheduled reports ("every Monday") run as durable jobs.
2. Mock the JMS SQS + WebSocket push in `mocks/jms`, using the `reports.ready` message (fixtures/jms_contract README §3).
3. The adapter can answer asynchronously.
done when: offline tests, including a restart in the middle of a job.
result: 2026-10-21, `git log --grep B-030`; 139 passed (228 with Postgres). Own job table instead of DBOS (reasons in jobs.py). No schedule UI yet; one worker per store.

### [x] B-031 · Exact answer cache
needs: offline
do: Key: normalised question + knowledge version + user scope + catalog version. A hit returns the same SQL with fresh execution and no model call. Never a semantic cache.
done when: offline test (second identical ask makes 0 model requests; cache invalidates after a knowledge edit).
result: 2026-10-21, `git log --grep B-031`; 140 passed (SQLite) and on Postgres 18.6.

### [x] B-032 · Budgets and rate limits
needs: offline
do: Add a `limits.cost_per_turn_usd` key using `UsageLimits(cost_limit=…)`; verify that genai-prices covers the configured models, falling back to the price table. Add a per-user requests-per-minute limit.
done when: offline tests; the config example stays ≤ 20 lines.
result: 2026-10-21, `git log --grep B-032`; 143 passed; config example 20 settings. genai-prices disagrees with list prices for Haiku/Gemini: cap scaled (doc 20 §2.2).

### [x] B-033 · Production compose
needs: docker
do: Add a `compose.prod.yml` with the bot, Postgres (B-026), optional TEI (B-028), Phoenix and oauth2-proxy, with health checks and volumes.
done when: `docker compose -f compose.prod.yml config` is valid and the stack starts locally; doc 13 §5 updated.
result: 2026-10-21, `git log --grep B-033`; stack started locally, all healthy (doc 13 §5). Real IdP sign-in not tested.

## Phase P3: product UI and operations

### [x] B-034 · Product front end (React, assistant-ui on AG-UI)
needs: node
do: **Research first** (assistant-ui vs CopilotKit vs alternatives). Build `web/` with Vite: report card, option and follow-up chips, feedback (words, undo), remember cards, requests. Serve the build from FastAPI. NiceGUI stays for admin.
done when: `npm run build` works, and Playwright smoke tests cover the main flows against a FunctionModel-backed server.
result: 2026-10-21, `git log --grep B-034`; npm run build OK, Playwright 2/2 passed. No chat framework (research in doc 10). Pins, drill, schedules and My knowledge are not in the React page yet (NiceGUI has them).

### [x] B-035 · Tracing on by default in compose (Phoenix)
needs: docker
do: Set up a `phoenix` service, `OTEL_EXPORTER_OTLP_ENDPOINT` in compose, and add the `otel` extra to the image.
done when: a trace appears for one ask (screenshot or API check).
result: 2026-10-21, `git log --grep B-035`; spans checked via Phoenix API for a scripted turn; containerised real-model trace not run (no key).

### [x] B-036 · Standalone login recipe
needs: docker
do: Add `deploy/auth/`: oauth2-proxy in front of the bot (`auth.mode: headers`), plus a Pocket ID option when no IdP exists. Map IdP groups to roles user/admin/owner.
done when: compose example plus a doc 13 section.
result: 2026-10-21, `git log --grep B-036`; header stripping verified against oauth2-proxy; also fixed X-User-* spoofing behind the proxy. Pocket ID sign-in not run end to end.

### [x] B-037 · Operator runbook
needs: offline
do: Write `docs/24-runbook.md`: backup/restore of `state.db`, upgrade, revalidate after target-DB migrations, rotating keys, moving to Postgres, exporting knowledge.
done when: the doc exists and is linked.
result: 2026-10-21, `git log --grep B-037`; plus tools/copy_state.py for the Postgres move (verified on the JMS catalogue).

## Phase P4: JMS track (all against the mock; no JMS access)

### [x] B-038 · Report Builder output profile
needs: offline
do: Add `adapters.jms` option `builder_compatible: true` (inside the adapter's own config section). The guard additionally rejects SQL outside the staging Builder grammar (reuse `mocks/jms/server.py::builder_grammar_problem`, moved into the adapter), so saved reports open editable.
done when: offline tests: the 8 grammar cases, and an agent retry when the grammar is violated.
result: 2026-10-21, `git log --grep B-038`; 148 passed. Grouped/aggregate reports are impossible in this mode (doc 10 §5).

### [x] B-039 · Save to Report Builder
needs: offline
do: The adapter offers a "Save to JMS" option, which calls a configurable host URL (the mock in tests) with the `custom_report` fields from fixtures/jms_contract README §4.
done when: offline test against the mock; editable or view-only is reported back to the user.
result: 2026-10-21, `git log --grep B-039`; 150 passed; tested against the mock only.

### [x] B-040 · Contract replay tests
needs: offline
do: Generate request/response examples from `fixtures/jms_contract/chat_contract.schema.json`, covering every `reports.action`, and validate the adapter's responses against the `ChatResponse` schema (jsonschema).
done when: the tests pass for all actions.
result: 2026-10-21, `git log --grep B-040`; all 8 actions schema-valid; 151 passed.

### [!] B-041 · Pilot against JMS staging
needs: human
do: Requires JMS access, which does not exist after the bundle leaves. Only a human with access can run it: refresh the snapshot, then pilot read-only.
done when: n/a for the agent.

## Data and verification

### [x] B-042 · Correlated synthetic data
needs: docker
do: Add a per-table correlation spec generated from the profile (e.g. stage given case_type, ordered dates created ≤ completed) under `tools/synth/correlations/`. **Research first** (NeMo Data Designer vs a hand-written spec). Re-generate, then re-run the 18-prompt eval.
done when: the spec is applied, tests check date ordering, and doc 12 is updated.
result: 2026-10-21, `git log --grep B-042`; date-order violations 9,809 -> 0 on the local MySQL. eval pending: needs llm (re-run the 18 prompts on the new data). Category correlations impossible from the profile.
eval 2026-10-21b: Sonnet 18 prompts on the new data: 13 reports, 5 clarify, 0 errors, $2.68.

### [x] B-043 · Visual UI check
needs: browser
do: Use browser automation to open each page for each role, perform a feedback / undo / request / edit flow, and save screenshots to `docs/screenshots/`.
done when: screenshots are committed and issues found are fixed.
result: 2026-10-21, `git log --grep B-043`; 11 screenshots, 0 console errors; fixed stale config copy and a local-path leak in screenshots. Done with Playwright's own Chromium (doctor's `browser` capability is false).

### [x] B-044 · Real LM Studio run
needs: lmstudio
do: Load a tool-calling model in LM Studio. Run the demo gold set with `models.agent: lmstudio:<id>`, then tune via B-012 profiles.
done when: `fixtures/demo_property/eval_results_lmstudio.json` exists and doc 20 §4 is updated with real numbers.
result: 2026-10-21, `git log --grep B-044`; gemma-4-e2b 1/10 content match, 2 errors -> 0 with output_retries 4 (accuracy unchanged); doc 20 §4.1.

### [!] B-045 · Gemini direct (Google API) run
needs: gemini
do: Run the demo gold set with `models.agent: google:<current Flash id>` (re-check the id first).
done when: a results file exists and doc 20 is updated.
blocked: 2026-10-21. The GEMINI_API_KEY in .env is on Google's free tier: gemini-3.8-flash allows 5 requests/minute, and all 10 demo questions failed with 429 RESOURCE_EXHAUSTED in under a second (one turn needs ~10 requests). Question for the user: provide a paid-tier key, or accept a throttled run (about 2 questions per minute at best, and the free tier's daily cap may still stop it)? Current id re-checked: gemini-3.8-flash; Google direct price added to llm.PRICES.

update 2026-10-21b: staggered free-tier runs as the user asked: gemini-3.8-flash exhausted its 20/day quota; gemini-3.5-flash-lite completed the demo gold set: 7/10, 0 errors, $0 (doc 20 §4.2). Paid-tier 3.8-flash still unmeasured directly.
## Accuracy layers from the 2026-10-21 research pass (doc 16 §5)

### [x] B-046 · Deterministic SQL-trap checks
result: 2026-10-21, 82b8ea9. `agent.sql_trap`: = NULL, NOT IN (subquery), LEFT JOIN undone by WHERE, SUM/AVG over a one-to-many join; one retry. Demo gold Sonnet 8/10 → 8/10, $0.236 → $0.242, no trap fired.

### [x] B-047 · Spelling fallback for stored values
result: 2026-10-21, 61c2992. RapidFuzz fallback in `search_values`. Two misspelled gold cases added (gp-11, gp-12); A/B in docs/08.

### [ ] B-048 · Low-confidence candidates with execution agreement
needs: llm
do: Behind a setting (default off), for turns that `_second_opinion` would review: 2 extra SQLs from the fast model, executed through `_run_report_sql`, compared with `same_result`. Agreement keeps the answer; disagreement goes to a judge given the retrieved knowledge (MaP-SQL style) or becomes a Clarify naming both readings ("Two Surfaces of Ambiguity", VLDB'26 AIDB).
done when: gold with the flag on and off, 3 runs each; content match, clarifications and cost recorded in doc 16 §5.

### [ ] B-049 · Back-translation in the second opinion
needs: llm
do: The reviewer restates the SQL in plain words before comparing with the question (`_second_opinion`, review output type). Measure concern precision/recall on gold against 1/4 precision, 1/1 recall (2026-10-21b).

### [ ] B-050 · SQL-skeleton similarity for confirmed examples
do: After a draft SQL exists, re-rank confirmed examples by skeleton similarity (sqlglot, literals stripped; Jaccard over node types and tables). Offline test first; then B-009-style eval with saved examples.

### [ ] B-051 · Optional cross-encoder rerank
do: fastembed `TextCrossEncoder` (ms-marco-MiniLM-L-6-v2, Apache, 80 MB) over the RRF top 30 in `search_knowledge` and `search_schema`, behind one setting, default off. Measure recall@5 with `tools/embed_compare.py` first; adopt only if recall moves.
