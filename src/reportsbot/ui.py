"""Local / pilot UI (NiceGUI). Pages by role (docs/22-roles-and-user-aids.md):

  /            Ask             everyone: chat, report cards, feedback (+ undo, + in words), fix requests, CSV
  /knowledge   My knowledge    everyone: what I taught (edit, share, withdraw, undo, history), shared
                               knowledge (request a fix), my requests; add personal knowledge
  /admin       Admin           admins/owners: review queue, open requests, add shared knowledge, export/import
  /config      Configuration   owners: edit reportsbot.yaml (validated), history, rollback

Identity comes from the URL (?user=alice&role=admin&team=ops; roles user|admin|owner) because this UI
is for local testing; a host application uses the HTTP API with its own login instead.
"""
from __future__ import annotations

import datetime as dt
import json

from fastapi import FastAPI
from nicegui import ui

from . import admin as admin_ops
from . import messages as msg
from .knowledge import User
from .service import App

_BADGE = {"verified": "positive", "yours": "primary", "adapted": "info", "new": "grey-7"}
_KINDS = ["term", "note", "join", "example"]


def _user(user: str, role: str, team: str | None) -> User:
    return User(id=user or "guest", role=role, team=team or None)  # role normalised by User


def _when(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _nav(u: User) -> None:
    q = f"?user={u.id}&role={u.role}" + (f"&team={u.team}" if u.team else "")
    with ui.header().classes("items-center gap-4 bg-slate-800"):
        ui.label("Reports").classes("text-lg font-semibold")
        ui.link("Ask", f"/{q}").classes("text-white")
        ui.link("My knowledge", f"/knowledge{q}").classes("text-white")
        if u.is_admin:
            ui.link("Admin", f"/admin{q}").classes("text-white")
        if u.is_owner:
            ui.link("Configuration", f"/config{q}").classes("text-white")
        ui.space()
        ui.label(f"{u.id} · {u.role}" + (f" · team {u.team}" if u.team else "")).classes("text-sm opacity-80")


def _safe(fn, *args, **kw):
    """Run an action and show its message; permission or validation problems become a red notice."""
    try:
        res = fn(*args, **kw)
        if isinstance(res, dict) and res.get("message"):
            ui.notify(res["message"])
        return res
    except (PermissionError, ValueError, KeyError) as e:
        ui.notify(str(e).strip("'\""), type="negative", multi_line=True)
        return None


def _request_dialog(app: App, u: User, kind: str, *, item_id=None, turn_id=None, title="Request a fix") -> None:
    with ui.dialog() as d, ui.card().classes("min-w-[32rem]"):
        ui.label(title).classes("font-medium")
        ui.label("Describe, in your own words, what should change. An "
                 + ("owner" if kind in ("access", "config") else "admin") + " will see it.").classes("text-sm")
        text = ui.textarea(placeholder="e.g. VIP should mean more than 500 spent, not 1000").classes("w-full")

        def send():
            if _safe(app.create_request, u, kind=kind, text=text.value or "", item_id=item_id, turn_id=turn_id):
                d.close()

        with ui.row():
            ui.button("Send request", on_click=send).props("color=primary")
            ui.button("Cancel", on_click=d.close).props("flat")
    d.open()


def _knowledge_dialog(app: App, u: User, on_done, item: dict | None = None) -> None:
    """Add (item=None) or edit one piece of knowledge."""
    with ui.dialog() as d, ui.card().classes("min-w-[40rem]"):
        ui.label("Edit" if item else ("Add shared knowledge" if u.is_admin else "Add knowledge for me")).classes("font-medium")
        kind = ui.select(_KINDS, value=(item or {}).get("kind", "term"), label="Kind").props("dense")
        if item:
            kind.disable()
        title = ui.input("Title (the word or report name)", value=(item or {}).get("title", "")).classes("w-full")
        question = ui.input("Question (examples)", value=(item or {}).get("question") or "").classes("w-full")
        body = ui.textarea("Meaning / rule in plain words", value=(item or {}).get("body") or "").classes("w-full")
        sql = ui.textarea("SQL (example: full query; term: condition; join: a.col = b.col)",
                          value=(item or {}).get("sql") or "").classes("w-full font-mono")

        def save():
            fields = {"title": title.value, "question": question.value or None, "body": body.value or None,
                      "sql": sql.value or None}
            if item:
                res = _safe(app.edit_knowledge, u, item["id"], fields)
            else:
                res = _safe(app.add_knowledge, u, kind=kind.value, **fields)
            if res:
                d.close()
                on_done()

        with ui.row():
            ui.button("Save", on_click=save).props("color=primary")
            ui.button("Cancel", on_click=d.close).props("flat")
    d.open()


def _history_dialog(app: App, item: dict) -> None:
    with ui.dialog() as d, ui.card().classes("min-w-[36rem]"):
        ui.label(f"History of “{item['title']}”").classes("font-medium")
        for e in app.knowledge.history(item["id"]):
            note = e["note"] or ""
            if e["action"] == "edited":
                try:
                    n = json.loads(note)
                    note = "; ".join(f"{k}: “{n['before'].get(k)}” → “{v}”" for k, v in n["after"].items())
                except (ValueError, KeyError):
                    pass
            ui.label(f"{_when(e['at'])} · {e['actor']} · {e['action']} {note}").classes("text-sm")
        ui.button("Close", on_click=d.close)
    d.open()


def mount_ui(api: FastAPI, app: App) -> None:
    # ------------------------------------------------------------------ Ask
    @ui.page("/")
    def chat(user: str = "guest", role: str = "user", team: str | None = None):
        u = _user(user, role, team)
        _nav(u)
        state = {"conversation_id": None, "correcting": None}
        feed = ui.column().classes("w-full max-w-5xl mx-auto gap-3 p-4")
        with feed:
            ui.chat_message(msg.say("welcome"), name="Reports", sent=False)
            pins = app.pinned(u)
            if pins:
                with ui.row().classes("gap-2 items-center"):
                    ui.label("Your pinned reports:").classes("text-sm opacity-70")
                    for p in pins:
                        ui.button(f"★ {p['title']}", on_click=lambda p=p: send(p["question"])).props(
                            "flat dense no-caps color=primary")
                        ui.button(icon="close", on_click=lambda p=p: (app.unpin(u, p["id"]), ui.notify(
                            "Unpinned."))).props("flat dense round size=xs").tooltip("Unpin")
            pinned_q = {p["question"] for p in pins}
            starters = [s for s in app.starter_questions(u) if s not in pinned_q]
            if starters:
                with ui.row().classes("gap-2"):
                    ui.label("Others often ask:").classes("text-sm opacity-70")
                    for s in starters:
                        ui.button(s, on_click=lambda s=s: send(s)).props("flat dense no-caps color=primary")

        async def send(text: str) -> None:
            text = (text or "").strip()
            if not text:
                return
            if state["correcting"]:
                text = f"Correction to the previous report: {text}"
                state["correcting"] = None
                box.props("placeholder=Ask for a report")
            with feed:
                ui.chat_message(text, name=u.id, sent=True)
                spinner = ui.spinner(size="lg")
            box.value = ""
            result = await app.ask(u, text, state["conversation_id"])
            spinner.delete()
            state["conversation_id"] = result["conversation_id"]
            with feed:
                render(result)

        def rerun(r: dict) -> None:
            with feed:
                render(app.rerun(u, r["turn_id"]))

        def render(r: dict) -> None:
            if r["kind"] == "report":
                with ui.card().classes("w-full"):
                    prov = r["provenance"]
                    ui.badge(prov["text"], color=_BADGE.get(prov["label"], "grey-7"))
                    ui.label(r["message"]).classes("text-base")
                    cols = [{"name": f"c{i}", "label": c, "field": f"c{i}", "sortable": True, "align": "left"}
                            for i, c in enumerate(r["columns"])]
                    rows = [{f"c{i}": v for i, v in enumerate(row)} | {"_k": n} for n, row in enumerate(r["rows"])]
                    ui.table(columns=cols, rows=rows, row_key="_k", pagination=15).classes("w-full")
                    with ui.expansion(msg.say("assumptions_header"), value=True).classes("w-full"):
                        for a in r["assumptions"]:
                            ui.label(f"• {a}")
                    with ui.expansion("Show SQL").classes("w-full"):
                        ui.code(r["sql"], language="sql").classes("w-full")
                    feedback_row(r)
                    with ui.row().classes("gap-2"):
                        for f in r.get("follow_ups") or []:
                            ui.button(f, on_click=lambda f=f: send(f)).props("flat dense no-caps color=primary")
                        ui.space()
                        ui.button("Re-run with today's data", on_click=lambda r=r: rerun(r)).props("flat dense")
                        ui.button("Pin", icon="star", on_click=lambda r=r: (app.pin(u, r["turn_id"]), ui.notify(
                            "Pinned: it now heads your starter row."))).props("flat dense")
                        ui.button("Download CSV", on_click=lambda r=r: ui.download.content(
                            app.turn_csv(u, r["turn_id"]), f"{r['title'][:60]}.csv")).props("flat dense")
                        ui.button("Request a fix", on_click=lambda r=r: _request_dialog(
                            app, u, "fix_report", turn_id=r["turn_id"])).props("flat dense")
                for s in r.get("suggestions") or []:
                    suggestion_card(s)
            elif r["kind"] == "clarify":
                with ui.card().classes("w-full"):
                    ui.label(r["intro"]).classes("text-sm opacity-70")
                    ui.label(r["why"]).classes("text-sm opacity-70")
                    picks = []
                    for q in r["questions"]:  # all questions answered in one turn
                        ui.label(q["question"]).classes("text-base font-medium")
                        picks.append((q["question"], ui.toggle(q["options"]).props("no-caps")))

                    def answer(picks=picks):
                        chosen = [f"{q} → {t.value}" for q, t in picks if t.value]
                        if len(chosen) == len(picks):
                            send("; ".join(chosen) if len(chosen) > 1 else picks[0][1].value)
                        else:
                            ui.notify("Pick one option for each question (or type your own answer below).")

                    ui.button("Run", on_click=answer).props("color=primary")
            elif r["kind"] == "answer":
                ui.chat_message(r["text"], name="Reports", sent=False)
                for s in r.get("suggestions") or []:
                    suggestion_card(s)
            else:
                ui.chat_message(r["message"], name="Reports", sent=False)

        def feedback_row(r: dict) -> None:
            row = ui.row().classes("items-center gap-2 w-full")

            def ask_state():
                row.clear()
                with row:
                    ui.label(msg.say("ask_feedback")).classes("text-sm")
                    ui.button("Yes, this is right", on_click=yes).props("color=positive outline")
                    ui.button("No, fix it", on_click=no).props("color=warning outline")

            def done_state(icon: str, color: str, text: str):
                row.clear()
                with row:
                    ui.icon(icon, color=color)
                    ui.label(text).classes("text-sm")
                    ui.button("Undo my feedback", on_click=undo).props("flat dense")

            def yes():
                res = _safe(app.feedback, u, r["turn_id"], "correct")
                if res:
                    done_state("check_circle", "positive", res["message"])

            def no():
                row.clear()
                with row:
                    words = ui.textarea(placeholder=msg.say("fix_prompt")).classes("flex-grow")

                    async def submit():
                        res = _safe(app.feedback, u, r["turn_id"], "wrong", words.value or "")
                        if not res:
                            return
                        done_state("edit", "warning", res["message"])
                        if res.get("correction"):
                            await send(res["correction"].removeprefix("Correction to the previous report: "))
                        else:
                            state["correcting"] = r["turn_id"]
                            box.props("placeholder=Describe what should change")

                    ui.button("Send", on_click=submit).props("color=warning")
                    ui.button("Cancel", on_click=ask_state).props("flat")

            def undo():
                if _safe(app.undo_feedback, u, r["turn_id"]):
                    ask_state()

            ask_state()

        def suggestion_card(s: dict) -> None:
            with ui.card().classes("w-full bg-amber-50") as card:
                ui.label(msg.say("remember_header")).classes("text-sm font-medium")
                ui.label(f"{s['title']}: {s['body']}")
                ui.label(msg.say("remember_scope_note")).classes("text-xs opacity-70")

                def act(accept: bool):
                    res = _safe(app.remember, u, s["id"], accept)
                    if res:
                        card.clear()
                        with card:
                            ui.label(res["message"]).classes("text-sm")

                with ui.row():
                    ui.button("Remember", on_click=lambda: act(True)).props("color=primary")
                    ui.button("No thanks", on_click=lambda: act(False)).props("flat")

        with ui.footer().classes("bg-white"):
            with ui.row().classes("w-full max-w-5xl mx-auto items-center"):
                box = ui.input(placeholder="Ask for a report").classes("flex-grow").on(
                    "keydown.enter", lambda: send(box.value))
                ui.button("Send", on_click=lambda: send(box.value))

    # ------------------------------------------------------------------ My knowledge
    @ui.page("/knowledge")
    def knowledge(user: str = "guest", role: str = "user", team: str | None = None):
        u = _user(user, role, team)
        _nav(u)
        body = ui.column().classes("w-full max-w-5xl mx-auto gap-3 p-4")

        def draw():
            body.clear()
            data = app.my_knowledge(u)
            with body:
                if data["notice"]:
                    ui.label(data["notice"]).classes("text-warning")
                with ui.row().classes("items-center w-full"):
                    ui.label("What I've taught the bot").classes("text-lg font-semibold")
                    ui.space()
                    ui.button("Add knowledge", on_click=lambda: _knowledge_dialog(app, u, draw)).props("outline")
                if not data["mine"]:
                    ui.label("Nothing yet. Confirm a report, accept a 'Remember this?' card, or add knowledge.")
                for item in data["mine"]:
                    item_card(item, own=True)
                ui.label("Shared knowledge I benefit from").classes("text-lg font-semibold mt-4")
                for item in data["shared"]:
                    item_card(item, own=False)
                ui.label("My requests").classes("text-lg font-semibold mt-4")
                mine = app.list_requests(u, status=None) if not u.is_admin else [
                    r for r in app.list_requests(u, status=None) if r["requester"] == u.id]
                if not mine:
                    ui.label("No requests. Use 'Request a fix' on a report or a shared item.").classes("text-sm")
                for r in mine:
                    ui.label(f"{_when(r['created_at'])} · {r['kind']} · {r['status']}: {r['text']}"
                             + (f" — {r['resolver']}: {r['resolution']}" if r["resolution"] else "")).classes("text-sm")

        def item_card(item: dict, own: bool):
            with ui.card().classes("w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.badge(item["kind"])
                    ui.label(item["title"]).classes("font-medium")
                    ui.space()
                    ui.label(item["label"]).classes("text-xs opacity-70")
                if item.get("question"):
                    ui.label(f"Question: {item['question']}").classes("text-sm")
                if item.get("body"):
                    ui.label(item["body"]).classes("text-sm")
                if item.get("sql"):
                    with ui.expansion("SQL"):
                        ui.code(item["sql"], language="sql")
                ui.label(f"Confirmed {item['confirmations']}× · used {item['uses']}× · reported wrong "
                         f"{item['rejections']}×").classes("text-xs opacity-60")
                with ui.row():
                    if app.knowledge.can_edit(u, item):
                        ui.button("Edit", on_click=lambda i=item: _knowledge_dialog(app, u, draw, i)).props("flat")
                    if own and item["status"] == "active":
                        ui.button("Share with everyone", on_click=lambda i=item: act(app.share, i)).props("flat")
                    if (own or u.is_admin) and item["status"] != "retired":
                        ui.button("Withdraw", on_click=lambda i=item: act(app.retire, i)).props("flat color=negative")
                    if own or u.is_admin:
                        ui.button("Undo last change", on_click=lambda i=item: act(app.restore, i)).props("flat")
                    if not own and not u.is_admin:
                        ui.button("Request a fix", on_click=lambda i=item: _request_dialog(
                            app, u, "fix_knowledge", item_id=i["id"])).props("flat")
                    ui.button("History", on_click=lambda i=item: _history_dialog(app, i)).props("flat")

        def act(fn, item):
            _safe(fn, u, item["id"])
            draw()

        draw()

    # ------------------------------------------------------------------ Admin
    @ui.page("/admin")
    def admin_page(user: str = "guest", role: str = "user", team: str | None = None):
        u = _user(user, role, team)
        _nav(u)
        body = ui.column().classes("w-full max-w-5xl mx-auto gap-3 p-4")

        def draw():
            body.clear()
            with body:
                if not u.is_admin:
                    ui.label("Only admins can manage shared knowledge.")
                    return
                with ui.row().classes("w-full items-center"):
                    queue = app.review_queue(u)
                    ui.label(f"Review queue ({len(queue)})").classes("text-lg font-semibold")
                    ui.space()
                    ui.button("Add shared knowledge", on_click=lambda: _knowledge_dialog(app, u, draw)).props("outline")
                    ui.button("Export / import", on_click=bulk_dialog).props("outline")
                for item in queue:
                    queue_card(item)
                reqs = app.list_requests(u)
                ui.label(f"Open requests ({len(reqs)})").classes("text-lg font-semibold mt-4")
                for r in reqs:
                    request_card(r)

        def queue_card(item):
            with ui.card().classes("w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.badge(item["kind"]); ui.badge(item["status"], color="warning")
                    ui.label(item["title"]).classes("font-medium")
                ui.label(f"Owner {item['owner']} · confirmed by {len(item['confirmers'])} people · "
                         f"reported wrong {item['rejections']}×").classes("text-xs opacity-70")
                for k in ("question", "body"):
                    if item.get(k):
                        ui.label(item[k]).classes("text-sm")
                if item.get("sql"):
                    ui.code(item["sql"], language="sql").classes("w-full")
                last = app.knowledge.history(item["id"])[-1]
                ui.label(f"Why it is here: {last['note'] or last['action']}").classes("text-xs")
                with ui.row():
                    ui.button("Share with everyone", on_click=lambda i=item: do(app.promote, i["id"], "org"))
                    if item.get("team"):
                        ui.button(f"Share with team {item['team']}",
                                  on_click=lambda i=item: do(app.promote, i["id"], "team")).props("outline")
                    ui.button("Edit first", on_click=lambda i=item: _knowledge_dialog(app, u, draw, i)).props("flat")
                    ui.button("Reject", on_click=lambda i=item: do(app.retire, i["id"])).props("flat color=negative")

        def request_card(r):
            with ui.card().classes("w-full"):
                ui.label(f"{r['requester']} · {r['kind']} · {_when(r['created_at'])}").classes("text-xs opacity-70")
                ui.label(r["text"])
                if r["item_id"]:
                    item = app.knowledge.get(r["item_id"])
                    if item:
                        ui.label(f"About: {item['kind']} “{item['title']}”").classes("text-sm")
                        ui.button("Edit that item", on_click=lambda i=item: _knowledge_dialog(app, u, draw, i)).props("flat dense")
                note = ui.input("Note to the requester").classes("w-full")
                with ui.row():
                    ui.button("Done", on_click=lambda r=r, n=note: do(app.resolve_request, r["id"], "done", n.value or ""))
                    ui.button("Decline", on_click=lambda r=r, n=note: do(app.resolve_request, r["id"], "declined",
                                                                         n.value or "")).props("flat color=negative")

        def bulk_dialog():
            with ui.dialog() as d, ui.card().classes("min-w-[48rem]"):
                ui.label("Everything the bot has learned (edit, then Import)").classes("font-medium")
                text = ui.textarea(value=admin_ops.export_knowledge(app, u)).classes("w-full font-mono").props("rows=24")

                def do_import():
                    res = _safe(admin_ops.import_knowledge, app, u, text.value or "")
                    if res:
                        for err in res["errors"]:
                            ui.notify(err, type="warning", multi_line=True)
                        d.close()
                        draw()

                with ui.row():
                    ui.button("Import", on_click=do_import).props("color=primary")
                    ui.button("Download", on_click=lambda: ui.download.content(text.value, "knowledge.yaml")).props("flat")
                    ui.button("Close", on_click=d.close).props("flat")
            d.open()

        def do(fn, *args):
            _safe(fn, u, *args)
            draw()

        draw()

    @ui.page("/review")
    def review_redirect(user: str = "guest", role: str = "user", team: str | None = None):
        ui.navigate.to(f"/admin?user={user}&role={role}" + (f"&team={team}" if team else ""))

    # ------------------------------------------------------------------ Configuration (owners)
    @ui.page("/config")
    def config_page(user: str = "guest", role: str = "user", team: str | None = None):
        u = _user(user, role, team)
        _nav(u)
        body = ui.column().classes("w-full max-w-5xl mx-auto gap-3 p-4")

        def draw():
            body.clear()
            with body:
                if not u.is_owner:
                    ui.label("Only owners can change the configuration. Admins and users can send a request "
                             "from My knowledge.")
                    ui.button("Request a configuration change",
                              on_click=lambda: _request_dialog(app, u, "config", title="Request a configuration change"))
                    return
                cfg = admin_ops.get_config(app, u)
                ui.label(f"Configuration · {cfg['path']}").classes("text-lg font-semibold")
                ui.label("About 10 values. Meaning is never configured here; the bot learns it. API keys stay in "
                         "environment variables. Changes are validated, kept in history, and apply after a restart.").classes("text-sm")
                text = ui.textarea(value=cfg["yaml"]).classes("w-full font-mono").props("rows=22")
                note = ui.input("Why are you changing it?").classes("w-full")
                ui.button("Save", on_click=lambda: (_safe(admin_ops.save_config, app, u, text.value or "",
                                                          note.value or ""), draw())).props("color=primary")
                ui.label("History").classes("font-medium mt-4")
                for e in cfg["history"]:
                    with ui.row().classes("items-center"):
                        ui.label(f"{_when(e['at'])} · {e['actor']} · {e['note'] or ''}").classes("text-sm")
                        ui.button("Roll back this change", on_click=lambda e=e: (
                            _safe(admin_ops.rollback_config, app, u, e["id"]), draw())).props("flat dense")

        draw()

    ui.run_with(api, title="Reports", storage_secret="local-dev-only", show_welcome_message=False)
