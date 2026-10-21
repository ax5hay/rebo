# JMS integration contract (captured 2026-10-21, for use without JMS)

Everything the bot needs to know about how JMS talks to a reports bot, captured from the
orchid-ai-intake-bot code while it was available. The adapter (`src/reportsbot/adapters/jms.py`)
and the mock (`mocks/jms/server.py`) implement this, and `tests/test_jms_adapter.py` checks it.
There is no other JMS dependency.

## 1. Authentication (from `backend/app/core/tenant_auth.py`)

- `Authorization: Bearer <JWT>`, **HS256**, shared secret (`CHATBOT_JWT_SECRET` on the JMS side,
  `REPORTSBOT_JWT_SECRET` here), `iss` must be `"orchid"`.
- Claims read: `iss`, `bot_type` (`intake` | `knowledge` | `reports`; the reports bot accepts
  only `reports`), `db_schema` (agency database), `subdomain`, `user_id`, `user_type`, plus
  optional `contact` / `case` claim blocks used by other bots. The current code also derives
  `tenant_id` and `region`.
- The WebSocket handshake passes the same token as the query parameter `?token=…`
  (`frontend/src/api/reportsWs.ts`).

## 2. Chat request and response (from `backend/app/models/domain/{rag,reports}.py`)

`chat_contract.schema.json` contains the exact JSON Schemas, generated from the real Pydantic models:

| Schema | Fields |
|---|---|
| `ChatMessageRequest` | `message`, `session`, `context`, `conflict_resolution`, `history`, `reports` |
| `ReportsInteraction` | `action` (`query`, `select_option`, `manual_select`, `confirm`, `reject`, `freetext`, `new_report`, `resume`), `option_id`, `reports_session_id`, `entity_bindings`, `contact_type`, `output_wants` |
| `ChatResponse` | 33 fields; the reports bot uses `message`, `sql`, `columns`, `rows`, `row_count`, `truncated`, `error`, `reports_phase`, `reports_session_id`, `reports_awaiting`, `reports_options`, `reports_allow_freetext`, `reports_freetext_prompt`, `reports_preview_only`, `reports_pickers`, `reports_llm_usage` |
| `ReportOption` | `option_id`, `label`, `description`, `sql`, `explanation`, `preview_*`, … |

Endpoint: `POST /api/v1/chat/{contact_id}` (the reports widget uses `0`).

## 3. Asynchronous delivery (from `backend/app/services/reports_agent/jobs.py`)

Long turns are queued to SQS (`REPORTS_JOBS_QUEUE_URL`), and the result is pushed over an API
Gateway WebSocket connection keyed by `(db_schema, admin_id)`:

```json
{"type": "reports.ready", "payload": <ChatResponse as JSON>}
```

The frontend accepts only messages with `type == "reports.ready"` (`frontend/src/utils/reportsReady.ts`).
Mocked since B-030: with `reports.async: true` the adapter answers at once with
`reports_phase: "working"` and a `job_id`, runs the turn as a durable job, and sends the ChatResponse
as `report_ready` to `notify_url`; `mocks/jms/server.py` stands in for SQS (`POST /mock/sqs`) and for
the WebSocket push (`/mock/ws/{user_id}` delivers `{"type": "reports.ready", "payload": …}`). The real
SQS/API Gateway path is not exercised (JMS is unreachable).

## 4. Saving a report into JMS (Report Builder)

JMS saves a bot report as a `custom_report` row: `report_query` = the SQL, `query_dict` empty,
`report_headers` = column labels, `hyperlink` unset. On open, JMS executes `report_query` live and
tries to re-translate it into the Builder form. The staging translator accepts only: one flat
SELECT; plain or aliased columns (no functions except `lower(col) LIKE '%x%'`); INNER/LEFT joins on
foreign keys; AND-ed filters with `= != > >= < <= IS NULL IS NOT NULL LIKE`. It rejects
`WITH, UNION, DISTINCT, GROUP BY, HAVING, ORDER BY, CASE, IN, BETWEEN, OR, NOT LIKE`. Anything else
opens view-only. Mocked by `mocks/jms/server.py::builder_grammar_problem` (8 test cases).

## 5. Data captured

| File | What | Real rows? |
|---|---|---|
| `../jms_staging/schema.sql` | full structure of staging (207 tables) | no |
| `../jms_staging/profile.json` | statistics + filtered categorical value lists + measured implicit references | aggregates only |
| `../jms_staging/eval.jsonl` | 18 PO-validated prompts (JMS-6723) | no |
| `../jms_staging/gold_custom_reports.jsonl` | 79 human-built staging reports: prompt + gold SQL; `prompt_quality` (`question` for 12, `title_only` for 67) and `scorable` (6) | SQL only (screened for personal literals) |
| `../jms_staging/eval_results_*.json` | measured bot runs | synthetic rows only |

## 6. Contract replay (B-040)

`tests/test_jms_contract.py` drives every `ReportsUserAction` (`query`, `select_option`,
`manual_select`, `confirm`, `reject`, `freetext`, `new_report`, `resume`) through the adapter with a
scripted model. Each request is validated against `ChatMessageRequest` (with `session` and `context`
as the frontend sends them) and each response against `ChatResponse`, using `jsonschema`. `resume`
returns the session's latest answer again without a new turn; `manual_select` is handled like typed
text (the bot has no pickers).
