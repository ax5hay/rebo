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
| `GET /api/knowledge/about?q=` | anyone | what the bot knows about a word: visible learned items by trust, tables/columns with descriptions, stored values |
| `GET /api/starter` | anyone | starter questions: the user's pinned reports first, then the most-used trusted reports |
| `POST /api/turns/{id}/pin` / `DELETE /api/knowledge/{id}/pin` | the asker / the owner | pin a report (flags your own example with the same SQL, or creates one) / unpin; both logged in the item's history |
| `GET /api/knowledge/export` / `POST /api/knowledge/import` `{yaml}` | admin | everything learned as editable YAML, and back |
| `GET/PUT /api/admin/config` `{yaml, note}`, `POST /api/admin/config/rollback/{id}` | owner | view/change/roll back `reportsbot.yaml` (validated, atomic, audited) |

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

## 4. MCP (`reportsbot mcp`, FastMCP 4.1, stdio)

Tools: `search_schema`, `describe_table`, `search_values`, `run_sql` (same guard and limits) and
`verified_reports` (shared knowledge only). Learning is not exposed over MCP, because a
confirmation needs an identified person. Example Claude Code config:

```json
{"mcpServers": {"reports": {"command": "uv", "args": ["run", "--directory", "/path/to/reports-bot", "--extra", "mcp", "reportsbot", "mcp"]}}}
```

## 5. Embedding into JMS (host adapter outline)

1. JMS backend proxies `/reports-bot/*` → bot `/api/*`, setting `X-User-Id` = admin id,
   `X-User-Role` = `curator` for admins with the reports-admin permission, and `X-User-Team` = agency id.
2. JMS UI renders the `/api/ask` payload with its own components, using the `messages.py` texts
   returned in the payload.
3. Optional **"Save to Report Builder"** button: the host converts `sql` with its own translator
   (`orchid/utils/report_query.py`). This stays in the host, so the bot stays database-agnostic
   (doc 14).
