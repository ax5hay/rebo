"""Build the made-up "Greenleaf Property Management" demo database (SQLite, no JMS, no Docker).

Shows the same bot on a different domain with only a config change:
    uv run python fixtures/demo_property/build.py                    # -> fixtures/demo_property/greenleaf.db
    REPORTSBOT_CONFIG=fixtures/demo_property/reportsbot.yaml uv run reportsbot bootstrap --describe
    REPORTSBOT_CONFIG=fixtures/demo_property/reportsbot.yaml uv run reportsbot serve

Deliberately realistic quirks for the bot to learn from people rather than config:
  * lease status is a lookup table with agency-style labels ("Active - Month to Month", ...)
  * maintenance.assigned_to points at staff WITHOUT a declared foreign key
  * a password_hash column the bot must never show
  * "late" payments are only derivable (paid_on > due_on), "occupied" only via an active lease
Deterministic (seed 42). Gold questions with reference SQL: gold.jsonl.
"""
from __future__ import annotations

import datetime as dt
import random
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "greenleaf.db"

SCHEMA = """
CREATE TABLE region (region_id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE building (building_id INTEGER PRIMARY KEY, region_id INTEGER NOT NULL REFERENCES region(region_id),
    name TEXT NOT NULL, street TEXT, city TEXT, built_year INTEGER, has_elevator INTEGER NOT NULL DEFAULT 0);
CREATE TABLE unit (unit_id INTEGER PRIMARY KEY, building_id INTEGER NOT NULL REFERENCES building(building_id),
    unit_number TEXT NOT NULL, bedrooms INTEGER NOT NULL, sqft INTEGER, monthly_rent NUMERIC NOT NULL,
    unit_type TEXT NOT NULL);
CREATE TABLE tenant (tenant_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, email TEXT, phone TEXT,
    password_hash TEXT, created TEXT NOT NULL, pets INTEGER NOT NULL DEFAULT 0);
CREATE TABLE lease_status (status_id INTEGER PRIMARY KEY, label TEXT NOT NULL, is_current INTEGER NOT NULL);
CREATE TABLE lease (lease_id INTEGER PRIMARY KEY, unit_id INTEGER NOT NULL REFERENCES unit(unit_id),
    tenant_id INTEGER NOT NULL REFERENCES tenant(tenant_id), status_id INTEGER NOT NULL REFERENCES lease_status(status_id),
    start_date TEXT NOT NULL, end_date TEXT, deposit NUMERIC);
CREATE TABLE payment (payment_id INTEGER PRIMARY KEY, lease_id INTEGER NOT NULL REFERENCES lease(lease_id),
    due_on TEXT NOT NULL, paid_on TEXT, amount NUMERIC NOT NULL, method TEXT);
CREATE TABLE staff (staff_id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, role TEXT NOT NULL,
    region_id INTEGER REFERENCES region(region_id), active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE maintenance (request_id INTEGER PRIMARY KEY, unit_id INTEGER NOT NULL REFERENCES unit(unit_id),
    opened TEXT NOT NULL, closed TEXT, category TEXT NOT NULL, priority TEXT NOT NULL, state TEXT NOT NULL,
    assigned_to INTEGER, cost NUMERIC);
"""
FIRST = ["Ava", "Liam", "Mia", "Noah", "Zoe", "Ethan", "Isla", "Omar", "Priya", "Chen", "Sofia", "Diego",
         "Hana", "Lucas", "Amara", "Felix", "Nora", "Ravi", "Elena", "Kofi"]
LAST = ["Patel", "Nguyen", "Garcia", "Smith", "Okafor", "Kim", "Rossi", "Muller", "Haddad", "Silva",
        "Brown", "Ito", "Kowalski", "Dubois", "Mensah", "Lopez"]
STATUSES = [(1, "Active - Fixed Term", 1), (2, "Active - Month to Month", 1), (3, "Notice Given", 1),
            (4, "Ended", 0), (5, "Evicted", 0), (6, "Pending Signature", 0)]


def d(x: dt.date) -> str:
    return x.isoformat()


def build(path: Path = DB, seed: int = 42) -> Path:
    rng = random.Random(seed)
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    today = dt.date(2026, 10, 1)
    regions = ["North", "South", "Riverside"]
    con.executemany("INSERT INTO region VALUES (?,?)", list(enumerate(regions, 1)))
    b_id = u_id = 0
    for r in range(1, 4):
        for _ in range(4):
            b_id += 1
            con.execute("INSERT INTO building VALUES (?,?,?,?,?,?,?)",
                        (b_id, r, f"{rng.choice(['Oak', 'Maple', 'Cedar', 'Birch', 'Willow'])} {rng.choice(['Court', 'House', 'Lofts', 'Gardens'])} {b_id}",
                         f"{rng.randint(1, 999)} {rng.choice(['High', 'Mill', 'Park', 'Church'])} St", regions[r - 1] + " City",
                         rng.randint(1960, 2022), int(rng.random() < 0.5)))
            for n in range(rng.randint(8, 16)):
                u_id += 1
                beds = rng.choice([0, 1, 1, 2, 2, 3])
                con.execute("INSERT INTO unit VALUES (?,?,?,?,?,?,?)",
                            (u_id, b_id, f"{n // 4 + 1}{n % 4 + 1:02d}", beds, 350 + beds * 300 + rng.randint(0, 150),
                             round(900 + beds * 450 + rng.randint(-100, 300), 2), "studio" if beds == 0 else "apartment"))
    con.executemany("INSERT INTO lease_status VALUES (?,?,?)", STATUSES)
    staff = []
    for s in range(1, 13):
        role = "technician" if s <= 8 else ("manager" if s <= 11 else "leasing agent")
        con.execute("INSERT INTO staff VALUES (?,?,?,?,?,?)",
                    (s, rng.choice(FIRST), rng.choice(LAST), role, (s - 1) % 3 + 1, int(s != 7)))
        if role == "technician":
            staff.append(s)
    t_id = l_id = p_id = 0
    for unit in range(1, u_id + 1):
        start = today - dt.timedelta(days=rng.randint(30, 1500))
        for _ in range(rng.choice([1, 1, 2])):
            t_id += 1
            created = start - dt.timedelta(days=rng.randint(5, 60))
            fn, ln = rng.choice(FIRST), rng.choice(LAST)
            con.execute("INSERT INTO tenant VALUES (?,?,?,?,?,?,?,?)",
                        (t_id, fn, ln, f"{fn}.{ln}{t_id}@example.com".lower(), f"555-01{t_id:02d}"[:12],
                         "$2b$12$" + "".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(53)),
                         d(created), int(rng.random() < 0.3)))
            ended = rng.random() < 0.35
            end = start + dt.timedelta(days=rng.randint(180, 720)) if ended else None
            status = rng.choice([4, 4, 4, 5]) if ended else rng.choice([1, 1, 1, 2, 2, 3, 6])
            l_id += 1
            con.execute("INSERT INTO lease VALUES (?,?,?,?,?,?,?)",
                        (l_id, unit, t_id, status, d(start), d(end) if end else None, rng.choice([500, 1000, 1500])))
            rent = con.execute("SELECT monthly_rent FROM unit WHERE unit_id=?", (unit,)).fetchone()[0]
            due = start
            last = min(end or today, today)
            late_prone = rng.random() < 0.2
            while due <= last and status != 6:
                p_id += 1
                paid = None if (due > today - dt.timedelta(days=20) and rng.random() < 0.3) else \
                    due + dt.timedelta(days=rng.randint(6, 25) if late_prone and rng.random() < 0.6 else rng.randint(-3, 2))
                con.execute("INSERT INTO payment VALUES (?,?,?,?,?,?)",
                            (p_id, l_id, d(due), d(paid) if paid else None, rent, rng.choice(["card", "transfer", "check"])))
                due = (due.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
            if ended:
                start = end + dt.timedelta(days=rng.randint(10, 60))
                if start > today:
                    break
    r_id = 0
    for _ in range(420):
        r_id += 1
        opened = today - dt.timedelta(days=rng.randint(0, 540))
        is_closed = rng.random() < (0.9 if opened < today - dt.timedelta(days=30) else 0.4)
        closed = opened + dt.timedelta(days=rng.randint(0, 21)) if is_closed else None
        category = rng.choice(["plumbing", "electrical", "heating", "appliance", "pest", "general"])
        con.execute("INSERT INTO maintenance VALUES (?,?,?,?,?,?,?,?,?)",
                    (r_id, rng.randint(1, u_id), d(opened), d(closed) if closed else None, category,
                     rng.choice(["low", "normal", "normal", "high", "urgent"]),
                     "closed" if is_closed else rng.choice(["open", "open", "in_progress", "waiting_parts"]),
                     rng.choice(staff) if rng.random() < 0.85 else None,
                     round(rng.uniform(40, 900), 2) if is_closed else None))
    con.commit()
    con.close()
    return path


if __name__ == "__main__":
    print(build())
