"""Durable jobs and scheduled reports (B-030)."""
import datetime as dt
import json

import httpx2 as httpx
import pytest

from rebo.agent import build_agent
from rebo.jobs import Jobs, next_run
from rebo.knowledge import User
from rebo.llm import build_model
from rebo.service import App
from test_learning import fake_turn
from test_llm import _completion

REPORT = _completion("present_report", {"title": "Paused", "assumptions": [],
                                        "sql": "SELECT full_name FROM customer WHERE status = 'paused'"})


def _model(app, calls):
    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=REPORT)
    app.__dict__["agent"] = build_agent(build_model("lmstudio:m", app.settings, http_client=httpx.AsyncClient(
        transport=httpx.MockTransport(handler))))


def test_next_run_understands_daily_weekdays_and_a_weekday():
    monday_9 = dt.datetime(2026, 10, 26, 9, 0).timestamp()           # a Monday
    assert dt.datetime.fromtimestamp(next_run("daily 08:00", monday_9)) == dt.datetime(2026, 10, 27, 8, 0)
    assert dt.datetime.fromtimestamp(next_run("monday 08:00", monday_9)) == dt.datetime(2026, 11, 2, 8, 0)
    friday_9 = dt.datetime(2026, 10, 30, 9, 0).timestamp()
    assert dt.datetime.fromtimestamp(next_run("weekdays 08:00", friday_9)) == dt.datetime(2026, 11, 2, 8, 0)
    with pytest.raises(ValueError):
        next_run("every so often", monday_9)


async def test_a_background_question_is_answered_and_announced(app):
    calls, sent = [], []
    _model(app, calls)
    app.settings.notify_url = "http://hooks.example.com"
    app.__dict__["notify_client"] = httpx.Client(transport=httpx.MockTransport(
        lambda r: sent.append(json.loads(r.content)) or httpx.Response(204)))
    alice = User("alice")
    jid = app.jobs.enqueue("ask", alice, {"text": "paused customers", "conversation_id": None})
    assert app.jobs.get(alice, jid)["status"] == "queued"
    assert await app.jobs.run_once() == jid and await app.jobs.run_once() is None
    job = app.jobs.get(alice, jid)
    assert job["status"] == "done" and job["result"]["kind"] == "report" and len(job["result"]["rows"]) == 10
    assert sent[-1]["event"] == "report_ready" and sent[-1]["job_id"] == jid
    with pytest.raises(KeyError):
        app.jobs.get(User("bob"), jid)


async def test_a_job_interrupted_by_a_restart_runs_again(app):
    calls = []
    jid = app.jobs.enqueue("ask", User("alice"), {"text": "paused customers"})
    started = app.jobs.claim()                                       # the old process took it, then died
    assert started["id"] == jid and started["status"] == "running"
    assert app.jobs.claim() is None                                  # still leased: nobody else runs it
    restarted = App(app.settings)                                    # a new process on the same state
    _model(restarted, calls)
    assert await Jobs(restarted).run_once(at=started["lease_until"] + 1) == jid
    job = restarted.jobs.get(User("alice"), jid)
    assert job["status"] == "done" and job["attempts"] == 2 and calls


async def test_a_scheduled_report_reruns_without_a_model(app):
    alice = User("alice")
    t = fake_turn(app, alice, "SELECT full_name AS customer FROM customer WHERE status = 'paused'")
    s = app.jobs.schedule(alice, t, "daily 08:00")
    assert app.jobs.due_schedules(at=s["next_at"] - 1) == 0
    assert app.jobs.due_schedules(at=s["next_at"] + 1) == 1 and app.jobs.due_schedules(at=s["next_at"] + 1) == 0
    jid = await app.jobs.run_once(at=s["next_at"] + 2)
    job = app.jobs.get(alice, jid)
    assert job["kind"] == "scheduled" and job["result"]["kind"] == "report" and len(job["result"]["rows"]) == 10
    usage = json.loads(app.store.one("SELECT usage FROM turn WHERE id=?", (job["result"]["turn_id"],))["usage"])
    assert usage["route"] == "rerun" and usage["requests"] == 0
    assert app.store.one("SELECT next_at FROM schedule WHERE id=?", (s["id"],))["next_at"] > s["next_at"]
    with pytest.raises(PermissionError):
        app.jobs.schedule(User("bob"), t, "daily 08:00")
