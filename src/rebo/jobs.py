"""Durable jobs and scheduled reports (B-030; docs/13 §7).

A job row is the unit of work: `ask` (a question answered in the background, e.g. the JMS adapter's
asynchronous mode) or `scheduled` (re-run a saved report, no model call). A worker claims a job with
a lease; if the process dies, the lease runs out and the next worker (after a restart) runs the job
again from the start. Answering a question twice is safe; nothing here writes to the reported
database. Finished work is announced through the notify_url webhook as `report_ready` (doc 22).

Why not DBOS (researched 2026-10-21: dbos 3.3.0, MIT): it adds psycopg, croniter, click and its own
system tables, and its gain, resuming a turn between LLM steps, is not needed when a scheduled report
needs no model and an interrupted question can simply be asked again. It stays the upgrade path.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from typing import TYPE_CHECKING, Any, Callable

from .knowledge import User
from .store import new_id, now

if TYPE_CHECKING:
    from .service import App

log = logging.getLogger(__name__)
LEASE_S = 300
MAX_ATTEMPTS = 3
_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def next_run(every: str, after: float) -> float:
    """Next time for "daily HH:MM", "weekdays HH:MM" or "<weekday> HH:MM" (server local time)."""
    parts = every.strip().lower().split()
    if len(parts) != 2 or ":" not in parts[1]:
        raise ValueError('Say when as "monday 08:00", "daily 07:30" or "weekdays 09:00".')
    day, hhmm = parts
    hour, minute = (int(x) for x in hhmm.split(":", 1))
    if day not in ("daily", "weekdays", *_DAYS) or not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError('Say when as "monday 08:00", "daily 07:30" or "weekdays 09:00".')
    start = dt.datetime.fromtimestamp(after)
    for add in range(0, 8):
        cand = (start + dt.timedelta(days=add)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if cand.timestamp() <= after:
            continue
        wd = cand.weekday()
        if day == "daily" or (day == "weekdays" and wd < 5) or (day in _DAYS and _DAYS.index(day) == wd):
            return cand.timestamp()
    raise AssertionError("unreachable: every pattern recurs within a week")


class Jobs:
    def __init__(self, app: "App"):
        self.app = app
        self.store = app.store

    # ---- queueing --------------------------------------------------------------------------
    def enqueue(self, kind: str, user: User, payload: dict[str, Any], run_after: float | None = None) -> str:
        jid = new_id("job")
        body = {**payload, "user": {"id": user.id, "role": user.role, "team": user.team}}
        with self.store.tx() as db:
            db.execute("INSERT INTO job(id, kind, owner, payload, status, attempts, run_after, created_at, updated_at)"
                       " VALUES(?,?,?,?,'queued',0,?,?,?)", (jid, kind, user.id, json.dumps(body),
                                                             run_after or now(), now(), now()))
        return jid

    def get(self, user: User, job_id: str) -> dict[str, Any]:
        j = self.store.one("SELECT * FROM job WHERE id=?", (job_id,))
        if not j or (j["owner"] != user.id and not user.is_admin):
            raise KeyError(job_id)
        return {**j, "payload": json.loads(j["payload"]), "result": json.loads(j["result"]) if j["result"] else None}

    def schedule(self, user: User, turn_id: str, every: str, deliver: dict | None = None) -> dict[str, Any]:
        self.app._turn(user, turn_id)  # only your own reports
        sid = new_id("sch")
        with self.store.tx() as db:
            db.execute("INSERT INTO schedule(id, owner, turn_id, every, deliver, next_at, active, created_at) "
                       "VALUES(?,?,?,?,?,?,1,?)", (sid, user.id, turn_id, every.strip(),
                                                   json.dumps(deliver) if deliver else None,
                                                   next_run(every, now()), now()))
        return self.store.one("SELECT * FROM schedule WHERE id=?", (sid,))

    def schedules(self, user: User) -> list[dict[str, Any]]:
        """Your active schedules, each with the question of the report it reruns (for lists people read)."""
        return self.store.all("SELECT s.*, t.question FROM schedule s LEFT JOIN turn t ON t.id = s.turn_id "
                              "WHERE s.owner=? AND s.active=1 ORDER BY s.next_at", (user.id,))

    def unschedule(self, user: User, schedule_id: str) -> None:
        s = self.store.one("SELECT owner FROM schedule WHERE id=?", (schedule_id,))
        if not s or s["owner"] != user.id:
            raise PermissionError("You can only stop your own schedules.")
        with self.store.tx() as db:
            db.execute("UPDATE schedule SET active=0 WHERE id=?", (schedule_id,))

    def due_schedules(self, at: float | None = None) -> int:
        """Queue a `scheduled` job for every schedule that is due, and move it to its next time."""
        at = at or now()
        n = 0
        for s in self.store.all("SELECT * FROM schedule WHERE active=1 AND next_at <= ?", (at,)):
            with self.store.tx() as db:
                moved = db.execute("UPDATE schedule SET next_at=? WHERE id=? AND next_at=?",
                                   (next_run(s["every"], at), s["id"], s["next_at"])).rowcount
            if moved:  # another worker did not take it first
                owner = User(s["owner"])
                self.enqueue("scheduled", owner, {"turn_id": s["turn_id"], "schedule_id": s["id"],
                                                  "deliver": json.loads(s["deliver"]) if s["deliver"] else None})
                n += 1
        return n

    # ---- running ---------------------------------------------------------------------------
    def claim(self, at: float | None = None) -> dict[str, Any] | None:
        """Take one runnable job: queued and due, or running with an expired lease (its worker died)."""
        at = at or now()
        for j in self.store.all("SELECT id, status, lease_until FROM job WHERE (status='queued' AND run_after <= ?) "
                                "OR (status='running' AND lease_until < ?) ORDER BY run_after LIMIT 5", (at, at)):
            with self.store.tx() as db:
                took = db.execute("UPDATE job SET status='running', lease_until=?, attempts=attempts+1, updated_at=? "
                                  "WHERE id=? AND status=? AND COALESCE(lease_until, 0)=?",
                                  (at + LEASE_S, now(), j["id"], j["status"], j["lease_until"] or 0)).rowcount
            if took:
                return self.store.one("SELECT * FROM job WHERE id=?", (j["id"],))
        return None

    async def run_once(self, at: float | None = None) -> str | None:
        """Claim and run one job; returns its id, or None when nothing is due."""
        job = self.claim(at)
        if not job:
            return None
        p = json.loads(job["payload"])
        user = User(p["user"]["id"], role=p["user"]["role"], team=p["user"]["team"])
        try:
            if job["kind"] == "ask":
                res = await self.app.ask(user, p["text"], p.get("conversation_id"))
            elif job["kind"] == "scheduled":
                res = self.app.rerun(user, p["turn_id"])
            else:
                raise ValueError(f"unknown job kind {job['kind']}")
        except Exception as e:
            failed = job["attempts"] >= MAX_ATTEMPTS
            log.warning("job %s attempt %s failed: %s", job["id"], job["attempts"], e)
            with self.store.tx() as db:
                db.execute("UPDATE job SET status=?, error=?, run_after=?, lease_until=NULL, updated_at=? WHERE id=?",
                           ("failed" if failed else "queued", str(e)[:500], now() + 30 * job["attempts"], now(),
                            job["id"]))
            return job["id"]
        with self.store.tx() as db:
            db.execute("UPDATE job SET status='done', result=?, lease_until=NULL, updated_at=? WHERE id=?",
                       (json.dumps(res, default=str), now(), job["id"]))
        result = json.loads(json.dumps(res, default=str))
        deliver = p.get("deliver") or {}
        fmt = self.app.deliver_formatters.get(deliver.get("kind", ""))
        self.app.notify("report_ready", job_id=job["id"], kind=job["kind"], user=user.id, deliver=p.get("deliver"),
                        result=result, **({"response": fmt(deliver, result)} if fmt else {}))
        return job["id"]

    async def worker(self, idle_s: float = 2.0, stop: Callable[[], bool] = lambda: False) -> None:
        """The background loop `rebo serve` runs: queue due schedules, run due jobs."""
        while not stop():
            try:
                self.due_schedules()
                if await self.run_once():
                    continue
            except Exception:
                log.exception("job worker error")
            await asyncio.sleep(idle_s)
