# 10 · API, UI and MCP

## 1. Identity

The bot has no login of its own. It trusts three headers set by the host application's gateway:

| Header | Required | Values |
|---|---|---|
| `X-User-Id` | yes | Stable user id from the host (JMS: admin id) |
| `X-User-Role` | no (`user`) | `user`, `admin` or `owner` (`member`/`curator` accepted as older names) |
| `X-User-Team` | no | Team/agency id for team-scoped sharing |

**Never expose `/api` directly to browsers.** Put it behind the host's authenticated proxy, which
overwrites these headers. The dev UI takes the same values from the URL query
(`/?user=alice&role=curator&team=ops`) and is for local use only.

## 2. Routes (`api.py`)

All responses are JSON. Errors: 400 bad input, 403 not allowed, 404 unknown id.

### `POST /api/ask`
```json
// request
{"text": "active surrogates in screening with sub-stage", "conversation_id": null}
// response: report
{"turn_id": "turn_…", "conversation_id": "conv_…", "kind": "report",
 "title": "Active surrogates in Screening with current substage",
 "message": "Here is Active surrogates in Screening with current substage. 3 rows.",
 "columns": ["case_number", "surrogate_case", "current_substage"],
 "rows": [[12, "Smith GC", "Background check"], …],  // illustrative values
 "truncated": false, "elapsed_ms": 41,
 "sql": "SELECT …",
 "assumptions": ["Surrogates are cases of type surrogate; active means …", "…"],
 "provenance": {"label": "new", "item_ids": [], "text": "New report · not checked by anyone yet"},
 "follow_ups": ["Break this down by sub-stage", "Only the last 30 days"],   // one-click drill-downs
 "suggestions": [{"id": "sg_…", "kind": "term", "title": "in intake", "body": "…", "sql": "…"}],
 "trace": [{"tool": "search_knowledge", "query": "…", "hits": 0}, {"tool": "describe_table", "table": "gc_case", "found": true}, …]}
// response: clarify
{"turn_id": "…", "conversation_id": "…", "kind": "clarify", "intro": "Quick check before I run this:",
 "why": "…", "questions": [{"question": "…", "options": ["…", "…"]}, …up to 3], "trace": […]}
// response: answer / error
{"kind": "answer", "text": "…", "suggestions": […]}   |   {"kind": "error", "message": "…"}
```
Pass the returned `conversation_id` on the next call to keep context, including corrections.

### `POST /api/turns/{turn_id}/feedback`
```json
{"verdict": "correct"}                    → {"message": "Thanks, saved. … only tunes the bot for you …", "item": {…}}
{"verdict": "wrong", "note": "optional"} → {"message": "… What should be different? …", "items": [...], "next": "correction"}
```
After `"next": "correction"`, send the user's text to `/api/ask` with the same `conversation_id`,
prefixed `"Correction to the previous report: "`.

### `POST /api/suggestions/{suggestion_id}`  `{"accept": true|false}` → `{"message", "item"?}`

### Knowledge
| Route | Who | Response |
|---|---|---|
| `GET /api/knowledge` | anyone | `{"mine": [...], "shared": [...], "notice": "2 of your saved items need a re-check …" \| null}`; each item has `label` (status text) |
| `GET /api/knowledge/{id}/history` | anyone | event list (doc 09) |
| `POST /api/knowledge/{id}/share` | owner | → `proposed` (curator owner: → `verified`) |
| `POST /api/knowledge/{id}/promote` `{"scope":"org"\|"team"}` | curator | → `verified` |
| `POST /api/knowledge/{id}/retire` `{"reason":""}` | owner / curator | → `retired` |
| `POST /api/knowledge/{id}/restore` | owner / curator | undo the last status change |
| `GET /api/review` | curator | items `proposed` or `quarantined`, oldest first |
| `POST /api/admin/revalidate` | curator | `{"checked", "unchanged", "repaired", "stale"}` |
| `GET /api/health` | anyone | `{"ok": true, "bootstrapped_at": …}` |
| `POST /api/knowledge` `{kind, title, body?, sql?, question?, scope?}` | anyone | add knowledge: admins → shared at once; users → personal |
| `PATCH /api/knowledge/{id}` `{title?, question?, body?, sql?}` | admin, or the owner of an unshared item | edit (SQL validated); history keeps before/after; `restore` undoes |
| `DELETE /api/turns/{id}/feedback` | the person who gave it | undo feedback (reverses everything it changed) |
| `POST /api/requests` `{kind: fix_knowledge / fix_report / access / config / other, text, item_id?, turn_id?}` | anyone | ask someone else to change something; routed to admins, or owners for access/config |
| `GET /api/requests?status=open` | anyone | users: their own; admins: admin-targeted + own; owners: all |
| `POST /api/requests/{id}/resolve` `{status: done / declined, resolution}` | admin (admin requests), owner (all) | the requester sees the note |
| `GET /api/turns/{id}/csv` | the asker | the report as CSV |
| `POST /api/turns/{id}/rerun` | the asker | "Re-run with today's data": same SQL, fresh rows, no model call; a new turn with `usage.route = "rerun"` |
| `POST /api/turns/{id}/drill` `{row, column?}` | the asker | the records behind one row of a grouped report; new turn, `usage.route = "drill"`, no model |
| `POST /api/review/bulk` `{item_ids, action: share / reject, note}` | admin | share with everyone or withdraw several items with one note; returns `done` and per-item `errors` |
| `POST /api/admin/config/preview` `{yaml}` | owner | what saving would do: `{ok, errors, changes}`; database and model names checked, nothing saved |
| `GET /api/admin/stats?days=90` | admin, owner | usage dashboard: confirmation per week, provenance mix, top questions, most reported wrong, open requests by age, cost per day |
| `GET /api/admin/preview?user=X&q=…&team=` | admin | the context block user X would get for that question, plus the knowledge items with owners |
| `POST /api/agui` (AG-UI `RunAgentInput`; `threadId` = conversation id) | the asker | one turn as an AG-UI event stream: `RUN_STARTED`, `STEP_STARTED`/`STEP_FINISHED` + `CUSTOM rebo.progress` per tool step as it happens, the answer as a text message, `CUSTOM rebo.result` (the `/api/ask` payload), `RUN_FINISHED` or `RUN_ERROR` (B-029) |
| `POST /api/jobs {text, conversation_id?}` / `GET /api/jobs/{id}` | the asker (admins may read any) | answer in the background as a durable job; poll it, or receive `report_ready` on `notify_url` |
| `POST /api/schedules {turn_id, every}` / `GET /api/schedules` / `DELETE /api/schedules/{id}` | the report's asker | re-run a report on a schedule (no model) |
| `GET /api/knowledge/about?q=` | anyone | what the bot knows about a word: visible learned items by trust, tables/columns with descriptions, stored values |
| `GET /api/starter` | anyone | starter questions: the user's pinned reports first, then the most-used trusted reports |
| `POST /api/turns/{id}/pin` / `DELETE /api/knowledge/{id}/pin` | the asker / the owner | pin a report (flags your own example with the same SQL, or creates one) / unpin; both logged in the item's history |
| `GET /api/knowledge/export` / `POST /api/knowledge/import` `{yaml, dry_run?}` | admin | everything learned as editable YAML, and back; `dry_run: true` returns `changes` and errors and applies nothing |
| `GET/PUT /api/admin/config` `{yaml, note}`, `POST /api/admin/config/rollback/{id}` | owner | view/change/roll back `rebo.yaml` (validated, atomic, audited) |

## 3. Dev UI (`ui.py`, NiceGUI 3.18 mounted on the same FastAPI app)

### `/` Ask
```
┌ Reports  Ask  My knowledge  Review queue                     alice · member ┐
│ Reports: Ask for any report in plain words, for example …                     │
│                                                   alice: active surrogates … │
│ ┌ report card (doc 06 §2) ───────────────────────────────────────────────┐   │
│ └─────────────────────────────────────────────────────────────────────────┘   │
│ ┌ Should I remember this for next time? ┐                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│ [ Ask for a report                                              ] [ Send ]    │
└──────────────────────────────────────────────────────────────────────────────┘
```
- Enter or **Send** → spinner → card. A conversation id is kept per browser tab.
- **No, fix it** shows `fix_prompt`, changes the input placeholder to "Describe what should
  change", and prefixes the next message as a correction.
- A clarification shows every question at once (toggle chips per question) and one **Run** button;
  the answers are sent together as `Q → A; Q → A`. Follow-up chips under a report send their text.

### `/knowledge` My knowledge
Two lists: *What I've taught the bot* (every status) and *Shared knowledge I benefit from*. Each card
shows kind, title, status label, question/body, collapsible SQL, "Confirmed n× · used n× · reported
wrong n×", and the actions **Share with everyone** (own, active), **Withdraw**, **Undo last change**
and **History** (a dialog of events).

### `/review` Review queue (curators)
Each card shows kind, status, title, owner, number of distinct confirmers, rejections, the SQL, and
"Why it is here" (the latest event note, e.g. "3 people confirmed this same query independently").
Buttons: **Share with everyone**, **Share with team X** (when the owner has a team), **Reject**.

## 4. MCP (`rebo mcp`, FastMCP 4.1, stdio)

Tools: `search_schema`, `describe_table`, `search_values`, `run_sql` (same guard and limits) and
`verified_reports` (shared knowledge only). Learning is not exposed over MCP, because a
confirmation needs an identified person. Example Claude Code config:

```json
{"mcpServers": {"reports": {"command": "uv", "args": ["run", "--directory", "/path/to/rebo", "--extra", "mcp", "rebo", "mcp"]}}}
```

## 5. Embedding into JMS (host adapter outline)

1. JMS backend proxies `/rebo/*` → bot `/api/*`, setting `X-User-Id` = admin id,
   `X-User-Role` = `curator` for admins with the reports-admin permission, and `X-User-Team` = agency id.
2. JMS UI renders the `/api/ask` payload with its own components, using the `messages.py` texts
   returned in the payload.
3. Optional **"Save to Report Builder"** (B-039): with `adapters: {jms: {save_url: <host URL>}}`
   every report answer also offers the option `save`. Choosing it POSTs the `custom_report` fields
   (`title`, `sql`, `created_by` = the JWT user id; fixtures/jms_contract README §4) to that URL and
   tells the user whether the saved report opens **editable** or **view-only** (with the host's
   reason). The host still translates the SQL with its own reader, so the bot stays
   database-agnostic. Tested against `mocks/jms/server.py` (`POST /mock/custom-reports`); combine
   with `builder_compatible: true` (B-038) so saved reports open editable.

**Report Builder profile (B-038).** `adapters: {jms: {builder_compatible: true}}` (instead of
`adapters: [jms]`) makes every report SQL the staging Report Builder can open as editable: one flat
SELECT, plain or aliased columns, INNER/LEFT joins, AND-ed simple filters, `lower(col) LIKE` as the
only function (`adapters/jms.py::builder_grammar_problem`; the JMS mock uses the same check). The
adapter registers it in `App.sql_checks`; the report validator turns a violation into one more
`ModelRetry` naming the problem. Consequence: totals, counts and grouped reports cannot be
produced in this mode (the Builder cannot express them); the bot then explains or asks. Off by
default, so core behaviour is unchanged (decision in HANDOFF §4).

## The product UI (`web/`)

`rebo serve` opens it at `/` when `web/dist` is built (`cd web && npm ci && npm run build`); the
older NiceGUI pages remain behind `rebo serve --nicegui`. Pages: **Ask** (start page with known
reports and recent conversations; live progress; answers with sortable data, highlighted reading,
drill into a summary row, confirm / fix in words / undo, run again, pin, schedule, CSV, ask an admin,
open trace), **What I taught** (lookup, defaults, saved knowledge with edit / share / undo / history /
withdraw, schedules, requests), **Review** and **Admin** (admins), **Insights** (admins, owners),
**Configuration** (owners). Screenshots: `docs/screenshots/`.

Design (second version, 2026-10-21): a calm, current product look, deliberately not the generic "AI"
style. Neutral canvas with white working surfaces, one deep green accent for trust and learning (not
the usual indigo or violet), amber reserved for how a question was read; no gradients; 12px panels,
8px controls, pill-shaped status; Instrument Sans for the interface and JetBrains Mono for queries
only (both self-hosted, OFL). Structure follows current production tools and research: a persistent
sidebar with sections and recent conversations (a drawer on phones), a ⌘K command palette (cmdk), secondary actions in a
menu so the answer stays calm (progressive disclosure), tables first and charts only for trends, one
focal health figure on Insights. From the human-AI interaction guidelines (Amershi et al., CHI 2019):
each answer says where it came from and why (trust pill, "How I read your question"), correction is
one click away and in words, and every action says whom it affects. From text-to-SQL verification
research (Berant et al. 2018; DIY, IUI 2021; SQLucid; EMNLP 2023): "What the query does" lists the
query as plain steps generated from its syntax tree, next to the data, so people can check an answer
without reading SQL. Libraries added for this: cmdk 1.1.1 (MIT), lucide-react 1.61 (ISC icons),
sonner 2.0.8 (MIT toasts).

Libraries (npm, 2026-10-21): React 19.3, react-aria-components 1.22.1 (Apache-2.0; accessible
unstyled primitives: tables with sorting, dialogs, toggle groups), TanStack Query 5.104, React Router
8.5, Observable Plot 0.6.17 (ISC; charts, loaded only on Insights), Vite 8.3. No chat framework:
assistant-ui 0.15 / CopilotKit 1.79 bring thread primitives the report cards would override, and
`@ag-ui/client` 1.0 targets AG-UI 1.x while the server's ag-ui-protocol is 0.1.22, so the page reads
the `/api/agui` stream with a 25-line SSE reader. Identity: the login proxy in production; locally,
the "Signed in as" picker (or `?user=…&role=…`), remembered in the browser.

Tests: `npx playwright test` (Playwright 1.64, headless Chromium) against `tests/web_server.py`
(shop DB, scripted model); CI runs them.
