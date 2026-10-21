"""Developer / pilot UI (NiceGUI). Three pages: chat, my knowledge, admin review.

Identity is taken from the URL (?user=alice&role=admin&team=ops; roles user|admin|owner) because this UI is for
local testing; a host application uses the HTTP API with its own login instead.
Layouts are described screen by screen in docs/09-api-and-ui.md.
"""
from __future__ import annotations

import datetime as dt

from fastapi import FastAPI
from nicegui import ui

from . import messages as msg
from .knowledge import User
from .service import App

_BADGE = {"verified": "positive", "yours": "primary", "adapted": "info", "new": "grey-7"}


def _user(user: str, role: str, team: str | None) -> User:
    return User(id=user or "guest", role=role, team=team or None)  # role normalised by User


def _nav(u: User) -> None:
    q = f"?user={u.id}&role={u.role}" + (f"&team={u.team}" if u.team else "")
    with ui.header().classes("items-center gap-4 bg-slate-800"):
        ui.label("Reports").classes("text-lg font-semibold")
        ui.link("Ask", f"/{q}").classes("text-white")
        ui.link("My knowledge", f"/knowledge{q}").classes("text-white")
        if u.is_admin:
            ui.link("Review queue", f"/review{q}").classes("text-white")
        ui.space()
        ui.label(f"{u.id} · {u.role}" + (f" · team {u.team}" if u.team else "")).classes("text-sm opacity-80")


def mount_ui(api: FastAPI, app: App) -> None:
    @ui.page("/")
    def chat(user: str = "guest", role: str = "user", team: str | None = None):
        u = _user(user, role, team)
        _nav(u)
        state = {"conversation_id": None, "correcting": None}
        feed = ui.column().classes("w-full max-w-5xl mx-auto gap-3 p-4")
        with feed:
            ui.chat_message(msg.say("welcome"), name="Reports", sent=False)

        async def send(text: str) -> None:
            text = (text or "").strip()
            if not text:
                return
            if state["correcting"]:
                text = f"Correction to the previous report: {text}"
                state["correcting"] = None
            with feed:
                ui.chat_message(text, name=u.id, sent=True)
                spinner = ui.spinner(size="lg")
            box.value = ""
            result = await app.ask(u, text, state["conversation_id"])
            spinner.delete()
            state["conversation_id"] = result["conversation_id"]
            with feed:
                render(result)

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
                    if r.get("follow_ups"):
                        with ui.row().classes("gap-2"):
                            for f in r["follow_ups"]:
                                ui.button(f, on_click=lambda f=f: send(f)).props("flat dense no-caps color=primary")
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
            with ui.row().classes("items-center gap-2") as row:
                ui.label(msg.say("ask_feedback")).classes("text-sm")

                def yes():
                    res = app.feedback(u, r["turn_id"], "correct")
                    row.clear()
                    with row:
                        ui.icon("check_circle", color="positive")
                        ui.label(res["message"]).classes("text-sm")

                def no():
                    res = app.feedback(u, r["turn_id"], "wrong")
                    state["correcting"] = r["turn_id"]
                    row.clear()
                    with row:
                        ui.icon("edit", color="warning")
                        ui.label(res["message"]).classes("text-sm")
                    box.props("placeholder=Describe what should change")

                ui.button("Yes, this is right", on_click=yes).props("color=positive outline")
                ui.button("No, fix it", on_click=no).props("color=warning outline")

        def suggestion_card(s: dict) -> None:
            with ui.card().classes("w-full bg-amber-50") as card:
                ui.label(msg.say("remember_header")).classes("text-sm font-medium")
                ui.label(f"{s['title']}: {s['body']}")
                ui.label(msg.say("remember_scope_note")).classes("text-xs opacity-70")

                def act(accept: bool):
                    res = app.remember(u, s["id"], accept)
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
                ui.label("What I've taught the bot").classes("text-lg font-semibold")
                if not data["mine"]:
                    ui.label("Nothing yet. Confirm a report or accept a 'Remember this?' card to start.")
                for item in data["mine"]:
                    item_card(item, own=True)
                ui.label("Shared knowledge I benefit from").classes("text-lg font-semibold mt-4")
                for item in data["shared"]:
                    item_card(item, own=False)

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
                    if own and item["status"] == "active":
                        ui.button("Share with everyone", on_click=lambda i=item: act(app.share, i)).props("flat")
                    if (own or u.is_admin) and item["status"] != "retired":
                        ui.button("Withdraw", on_click=lambda i=item: act(app.retire, i)).props("flat color=negative")
                    if own or u.is_admin:
                        ui.button("Undo last change", on_click=lambda i=item: act(app.restore, i)).props("flat")
                    ui.button("History", on_click=lambda i=item: show_history(i)).props("flat")

        def act(fn, item):
            try:
                ui.notify(fn(u, item["id"])["message"])
            except PermissionError as e:
                ui.notify(str(e), type="negative")
            draw()

        def show_history(item):
            with ui.dialog() as d, ui.card().classes("min-w-[32rem]"):
                ui.label(f"History of “{item['title']}”").classes("font-medium")
                for e in app.knowledge.history(item["id"]):
                    when = dt.datetime.fromtimestamp(e["at"]).strftime("%Y-%m-%d %H:%M")
                    ui.label(f"{when} · {e['actor']} · {e['action']} {e['note'] or ''}").classes("text-sm")
                ui.button("Close", on_click=d.close)
            d.open()

        draw()

    @ui.page("/review")
    def review(user: str = "guest", role: str = "user", team: str | None = None):
        u = _user(user, role, team)
        _nav(u)
        body = ui.column().classes("w-full max-w-5xl mx-auto gap-3 p-4")

        def draw():
            body.clear()
            with body:
                if not u.is_admin:
                    ui.label("Only admins can review shared knowledge.")
                    return
                queue = app.review_queue(u)
                ui.label(f"Review queue ({len(queue)})").classes("text-lg font-semibold")
                for item in queue:
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
                            ui.button("Share with everyone", on_click=lambda i=item: do(app.promote, i, "org"))
                            if item.get("team"):
                                ui.button(f"Share with team {item['team']}",
                                          on_click=lambda i=item: do(app.promote, i, "team")).props("outline")
                            ui.button("Reject", on_click=lambda i=item: do(app.retire, i)).props("flat color=negative")

        def do(fn, item, *args):
            ui.notify(fn(u, item["id"], *args)["message"])
            draw()

        draw()

    ui.run_with(api, title="Reports", storage_secret="local-dev-only", show_welcome_message=False)
