# 22 · Roles and user aids

Who can change what, and every aid that helps people get the right report with the fewest turns.
Code: `knowledge.py` (`User`, `can_edit`, `edit`, `add`, `restore`, `undo_feedback`), `service.py`
(`feedback`, `undo_feedback`, `create_request`, `list_requests`, `resolve_request`, `edit_knowledge`,
`add_knowledge`, `starter_questions`, `turn_csv`), `admin.py` (configuration, export/import),
`api.py`, `ui.py`. Tests: `test_editing.py`, `test_feedback_and_requests.py`, `test_admin.py`.

## 1. Roles

Identity comes from the host (headers `X-User-Id`, `X-User-Role`, `X-User-Team`, or a JWT with
`role`), from the dev UI's URL, or from the CLI (which acts as an owner, since it has server access).
`member` and `curator` are accepted as older names for `user` and `admin`.

| Capability | user | admin | owner | Where |
|---|---|---|---|---|
| Ask; see provenance and assumptions; download CSV | ✓ | ✓ | ✓ | Ask page, `POST /api/ask`, `GET /api/turns/{id}/csv` |
| **Yes, this is right** / **No, fix it** (buttons, or **in their own words**) | ✓ | ✓ | ✓ | Ask page, `POST /api/turns/{id}/feedback` |
| **Undo my feedback** (or change it: new feedback replaces the old) | ✓ (own turns) | ✓ (own turns) | ✓ (own turns) | Ask page, `DELETE /api/turns/{id}/feedback` |
| Remember / dismiss a suggested fact | ✓ | ✓ | ✓ | Ask page, `POST /api/suggestions/{id}` |
| Add knowledge **for myself** (term, note, join, example) | ✓ | (adds shared) | (adds shared) | My knowledge, `POST /api/knowledge` |
| Edit / withdraw / undo **my own unshared** knowledge | ✓ | ✓ | ✓ | My knowledge, `PATCH /api/knowledge/{id}` |
| Ask to share my item with everyone | ✓ | (shares directly) | (shares directly) | `POST /api/knowledge/{id}/share` |
| **Request a fix** to shared knowledge or a report, **in words** | ✓ | ✓ | ✓ | Ask page, My knowledge, `POST /api/requests` |
| Request access to data / a configuration change | ✓ | ✓ | ✓ | Configuration page (non-owners), `POST /api/requests` kind `access`/`config` |
| See my requests and the answers | ✓ | ✓ | ✓ | My knowledge, `GET /api/requests` |
| Add / edit / share / withdraw / undo **any** knowledge | | ✓ | ✓ | My knowledge, Admin, `PATCH`/`POST` routes |
| Review queue (proposed, quarantined); resolve fix requests | | ✓ | ✓ | Admin, `GET /api/review`, `POST /api/requests/{id}/resolve` |
| Export / import everything learned (editable YAML) | | ✓ | ✓ (CLI too) | Admin, `GET /api/knowledge/export`, `POST /api/knowledge/import`, `reportsbot knowledge export/import` |
| Re-check knowledge after schema changes | | ✓ | ✓ | `POST /api/admin/revalidate`, `reportsbot revalidate` |
| View / change / roll back configuration; resolve access and config requests | | | ✓ | Configuration page, `GET/PUT /api/admin/config`, `POST /api/admin/config/rollback/{id}` |
| Bootstrap the database, serve, export the bundle | | | ✓ (server access) | CLI |

Rules behind the table:
- A user can never change what other people get. Their teaching is personal until 3 people agree
  and an admin approves it, or an admin adds it directly.
- An admin's edits apply to everyone at once, are logged with the before and after text, and are
  undoable step by step.
- Configuration never contains domain meaning (AGENTS.md §3), so owners change wiring and limits only.
  Hand-editing `reportsbot.yaml` on the server is equivalent; `reportsbot config check` validates it.

## 2. User aids that exist today

| Aid | What the person sees | Why it saves turns or errors |
|---|---|---|
| Provenance badge | "Verified report · checked by …" / "Same as a report you confirmed" / "Built from saved knowledge" / "New report" | Trust at a glance; fewer re-checks |
| Assumptions in plain words | "How I read your question" list | Wrong readings are spotted before anyone uses the numbers |
| One-turn clarification | Up to 3 questions with option chips and one **Run** | One clarifying turn instead of several |
| Remembered clarification answers | Picking an option stores a personal note (title = the question, body = the answer) shown in My knowledge, withdrawable there; free text that is not an option is not stored | The same question is not asked twice (B-007) |
| Favourites (pin a report) | **Pin** on a report; "Your pinned reports" heads the Ask page, each with an unpin ×; pinned questions also lead `GET /api/starter` | One click re-runs a favourite with no model call (route `direct`) (B-016) |
| "What do you know about X?" | Search box on My knowledge (`GET /api/knowledge/about?q=`): learned items grouped as Verified / Yours / Not yet shared, matching tables and columns with descriptions, stored values. In chat, a `Reply` lists the items it relied on ("From: …") | People see what the bot already knows before asking or teaching; no model call for the lookup (B-017) |
| Re-run with today's data | Button on every report | Same SQL, fresh rows, no model call (B-008) |
| Follow-up chips | Up to 3 drill-downs under each report | Drill down with one click |
| Starter questions | "Others often ask: …" from the most-used trusted reports | First question lands on a known-good report |
| Feedback in full words | **No, fix it** opens a text box; the words become the correction and run immediately | One step instead of two; the reason is kept with the feedback |
| Undo my feedback / change my mind | "Undo my feedback" after any confirmation or rejection | Mistaken clicks never stick; everything the feedback changed is reversed |
| Remember this? cards | The rule behind a correction, offered for next time ("Only for you") | The same correction is never needed twice |
| Request a fix | Text box on reports and shared items, routed to admins (or owners for access/config); answers shown under My requests | Users are never stuck with shared knowledge they cannot change |
| History with before → after | Every item: who did what, when, with the old and new text | Accountability; easy undo |
| CSV download | Button on every report | Take the data elsewhere without asking again |
| Stale notice | "N of your saved items need a re-check because the data they use changed" | Silent breakage after migrations becomes visible |

## 3. User aids to add next (proposed; each is one small commit)

| Aid | Who | Sketch |
|---|---|---|
| **"Why did you ask me that?"** | everyone | Show the evidence behind a clarification: the competing readings and their row counts (needs the deterministic ask-gate, doc 18 P1.2) |
| **Re-run with today's data** | everyone | Button on any past report; reuses the SQL, no model call |
| **Explain this number** | everyone | Click a cell to see the rows behind it (drill-through: same SQL with a filter on that group) |
| **Personal defaults** | everyone | "Always last 30 days unless I say otherwise", "only my region": saved as personal notes, shown as assumptions |
| **See as user X** | admin | Preview what a user's answer would use (their personal + shared knowledge) before sharing or editing |
| **Diff and approve imports** | admin | Show the changes an import would make before applying it |
| **Bulk review** | admin | Approve or reject several queue items at once, with one note |
| **Request SLA / notifications** | admin/owner | Age of open requests; email/webhook when a request is answered or an item goes stale |
| **Usage dashboard** | admin/owner | Confirmation rate, top questions, cost per day, items most reported wrong |
| **Config change preview** | owner | Validate a new configuration and run the offline tests plus a 5-question eval before saving |
| **Scheduled reports** | everyone | "Send me this every Monday" (needs durable jobs, doc 18 P2.5) |
