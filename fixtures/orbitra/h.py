"""Short generator helpers used by the table specs (spec_*.py)."""
from __future__ import annotations

import datetime as dt
import hashlib
import string

from engine import CURRENCY, END, NOW, START, B, BI, D, I, N, N4, S, TS, TX, Col, Ctx, Table, col, fk  # noqa: F401

UP = string.ascii_uppercase
INDIAN_STATES = [("27", "Maharashtra"), ("29", "Karnataka"), ("33", "Tamil Nadu"), ("07", "Delhi"), ("24", "Gujarat"),
                 ("36", "Telangana"), ("09", "Uttar Pradesh"), ("19", "West Bengal"), ("06", "Haryana"), ("08", "Rajasthan"),
                 ("32", "Kerala"), ("23", "Madhya Pradesh"), ("21", "Odisha"), ("03", "Punjab")]


def get(r: dict, path: str):
    """'order_date' or '@sales_order_id.order_date' (through a referenced parent row)."""
    cur = r
    for part in path.split("."):
        if cur is None:
            return None
        cur = cur.get(part)
    return cur


def cc(src: str | None = None) -> Col:
    """The row's country (hidden): drawn from the company's customer/people mix, or the parent's."""
    if src:
        return col("_cc", "str2", lambda r, g: get(r, src) or "IN")
    return col("_cc", "str2", lambda r, g: g.country())


def fake(attr: str, *args, **kw):
    return lambda r, g: getattr(g.faker(r.get("_cc") or "IN"), attr)(*args, **kw)


def ch(items, weights=None):
    return lambda r, g: g.pick(items, weights)


def rng(lo: int, hi: int):
    return lambda r, g: g.int(lo, hi)


def money(lo: float, hi: float, step: float = 1.0, skew: float = 1.6):
    return lambda r, g: g.money(lo, hi, step, skew)


def when(start: dt.date = START, end: dt.date = END, growth: float = 1.6):
    return lambda r, g: g.date(start, end, growth)


def after(path: str, lo: int, hi: int):
    return lambda r, g: g.after(get(r, path), lo, hi)


def stamp(path: str, start_h: int = 8, end_h: int = 19):
    return lambda r, g: g.ts(get(r, path), start_h, end_h)


def code(prefix: str, width: int = 6):
    return lambda r, g: g.code(prefix, r["_i"], width)


def const(v):
    return lambda r, g: v


def yes(p: float):
    return lambda r, g: g.chance(p)


def copy(path: str):
    return lambda r, g: get(r, path)


def currency_of(path: str = "_cc"):
    return lambda r, g: CURRENCY.get(get(r, path) or "IN", "INR")


def age_status(path: str, steps: list[tuple[int, list[str], list[int]]], default: str):
    """Status from the age of a date: e.g. orders older than 30 days are mostly delivered. steps is
    [(min_age_days, choices, weights), ...] from the oldest bracket down."""
    def gen(r, g):
        d = get(r, path)
        if d is None:
            return default
        if isinstance(d, dt.datetime):
            d = d.date()
        age = (END - d).days
        for min_age, choices, weights in steps:
            if age >= min_age:
                return g.pick(choices, weights)
        return default
    return gen


def person_name(part: str):
    """first or last name in the row's locale, kept consistent within the row."""
    def gen(r, g):
        if "_name" not in r:
            f = g.faker(r.get("_cc") or "IN")
            gender = r.get("gender")
            male = gender == "Male" if gender in ("Male", "Female") else g.chance(0.58)
            r["_name"] = ((f.first_name_male() if male else f.first_name_female()), f.last_name())
        return r["_name"][0 if part == "first" else 1]
    return gen


def email_of(domain: str | None = None):
    """first.last@domain; a number is added only when that address is taken, as mail admins do."""
    def gen(r, g):
        first, last = r.get("_name") or ("user", str(r["_i"]))
        clean = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())  # noqa: E731
        dom = domain or g.pick(["gmail.com", "outlook.com", "yahoo.co.in", "hotmail.com", "proton.me"],
                               [40, 20, 15, 10, 5])
        taken = g.__dict__.setdefault("_emails", set())
        base, n = f"{clean(first)}.{clean(last)}", 1
        addr = f"{base}@{dom}"
        while addr in taken:
            n += 1
            addr = f"{base}{n}@{dom}"
        taken.add(addr)
        return addr
    return gen


# Rough INR value of one unit of each currency, to size amounts in the local currency.
INR_PER = {"INR": 1.0, "USD": 83.0, "GBP": 105.0, "EUR": 90.0, "SGD": 62.0, "AED": 22.6, "AUD": 55.0, "JPY": 0.56}


def local(amount_inr: float, currency: str | None) -> float:
    """An INR-sized amount expressed in `currency`, rounded the way prices are."""
    v = amount_inr / INR_PER.get(currency or "INR", 1.0)
    return round(v, 0 if currency == "JPY" else 2)


def money_in(path: str, lo_inr: float, hi_inr: float, step: float = 1.0, skew: float = 1.6):
    """An amount drawn in INR terms, expressed in the currency found at `path`."""
    return lambda r, g: local(g.money(lo_inr, hi_inr, step, skew), get(r, path))


PHONE = {"GB": "+44 7### ######", "US": "+1 ###-###-####", "DE": "+49 1## #######", "FR": "+33 6 ## ## ## ##",
         "NL": "+31 6 ########", "AU": "+61 4## ### ###", "SG": "+65 9### ####", "AE": "+971 5# ### ####",
         "JP": "+81 90-####-####", "ES": "+34 6## ### ###", "IE": "+353 8# ### ####"}


def phone():
    def gen(r, g):
        c = r.get("_cc") or "IN"
        if c == "IN":
            return f"+91 {g.pick('6789')}{g.int(100000000, 999999999)}"
        return g.faker("US").numerify(PHONE.get(c, "+1 ###-###-####"))
    return gen


def pan(kind: str = "C"):
    """Indian PAN: 3 letters, entity type (C company, P person), 1 letter, 4 digits, 1 letter."""
    return lambda r, g: "".join(g.pick(UP) for _ in range(3)) + kind + g.pick(UP) + f"{g.int(1000, 9999)}" + g.pick(UP)


def gstin():
    def gen(r, g):
        if (r.get("_cc") or "IN") != "IN":
            return None
        state = r.get("_state") or g.pick(INDIAN_STATES)[0]
        p = "".join(g.pick(UP) for _ in range(3)) + "C" + g.pick(UP) + f"{g.int(1000, 9999)}" + g.pick(UP)
        return f"{state}{p}{g.int(1, 9)}Z{g.pick(UP + '0123456789')}"
    return gen


def vat_no():
    def gen(r, g):
        c = r.get("_cc") or "IN"
        if c == "IN":
            return None
        return f"{c if c != 'GB' else 'GB'}{g.int(100000000, 999999999)}"
    return gen


def ifsc():
    banks = ["HDFC", "ICIC", "SBIN", "UTIB", "KKBK", "YESB", "IDFB", "PUNB"]
    return lambda r, g: f"{g.pick(banks)}0{g.int(100000, 999999)}"


def secret():
    """A password hash or token: a protected column the bot must never show."""
    return lambda r, g: "$2b$12$" + hashlib.sha256(f"{r['_i']}-{g.rnd.random()}".encode()).hexdigest()[:53]


def street():
    return lambda r, g: g.faker(r.get("_cc") or "IN").street_address().replace("\n", ", ")


def city():
    return lambda r, g: g.faker(r.get("_cc") or "IN").city()


def postcode():
    return lambda r, g: g.faker(r.get("_cc") or "IN").postcode()


def company_name():
    suffix = {"IN": ["Pvt Ltd", "Ltd", "LLP", "Industries", "Enterprises", "Power Systems", "Infra"],
              "GB": ["Ltd", "plc", "Group"], "US": ["Inc.", "LLC", "Corp."], "DE": ["GmbH", "AG"],
              "FR": ["SA", "SAS"], "NL": ["B.V."], "SG": ["Pte Ltd"], "AE": ["LLC", "FZE"], "AU": ["Pty Ltd"],
              "ES": ["S.L."], "IE": ["Ltd"], "JP": ["K.K."]}
    def gen(r, g):
        c = r.get("_cc") or "IN"
        f = g.faker(c)
        base = f.last_name() if g.chance(0.5) else f.company().split(",")[0].split(" ")[0]
        mid = g.pick(["", " Energy", " Utilities", " Solar", " Power", " Electricals", " Infra", " Mobility",
                      " Renewables", " Grid", " Technologies", " Distribution"])
        if mid.strip() and mid.strip().lower() in base.lower():
            mid = ""
        end = g.pick([x for x in suffix.get(c, ["Ltd"]) if not (set(x.lower().split()) & set((base + mid).lower().split()))] or ["Ltd"])
        return f"{base}{mid} {end}".replace("  ", " ")
    return gen


def ascii_slug(text_: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFKD", text_).encode("ascii", "ignore").decode()
    return "".join(c for c in t.lower() if c.isalnum())


_VERB = ["Review", "Follow up on", "Update", "Fix", "Escalate", "Schedule", "Prepare", "Confirm", "Reconcile", "Approve", "Investigate",
         "Replace", "Validate", "Close", "Document", "Plan", "Check", "Resolve", "Track", "Finalise"]
_OBJ = ["meter firmware rollout", "inverter warranty claim", "GST reconciliation", "charger commissioning", "site survey", "pending purchase orders",
        "customer payment delay", "tender documents", "BIS certification", "spare parts stock", "SLA breach", "RF mesh coverage", "data concentrator outage",
        "quarterly forecast", "vendor onboarding", "safety audit observations", "billing mismatch", "OCPP integration", "installation schedule",
        "e-way bill errors", "price revision", "customer training", "AMC renewal", "battery backup failures", "export documentation", "travel claims",
        "CT ratio settings", "net metering approval", "load test results", "dispatch delay"]
_TAIL = ["", "", "for Pune plant", "before quarter close", "with the customer", "at site", "for the Hosur line", "this week", "for the UK depot",
         "with finance", "for the tender", "for Q3", "with the supplier", "in Bengaluru", "for the Middle East region"]


def phrase(r, g) -> str:
    return " ".join(x for x in (g.pick(_VERB), g.pick(_OBJ), g.pick(_TAIL)) if x)


def words(n_lo: int = 4, n_hi: int = 12):
    """A short business phrase (task, subject, reason). Faker's lorem text reads as obviously fake."""
    def gen(r, g):
        s = phrase(r, g)
        if n_hi > 10 and g.chance(0.5):
            s += "; " + phrase(r, g).lower()
        return s
    return gen


def paragraph():
    """A few sentences, as in a ticket comment."""
    openers = ["Customer reports that", "On site we found that", "Logs show that", "As discussed on the call,", "Update:", "Root cause:"]
    issues = ["the device stopped reporting after the firmware update", "the charger faults at around 40 kW", "readings are missing for two days",
              "the invoice shows the wrong tariff", "the RFID card is not recognised", "the inverter trips at noon on hot days",
              "the portal login fails with MFA", "the SIM was deactivated by the operator", "the CT wiring was reversed",
              "the payment was received but not applied"]
    closers = ["Will update by tomorrow.", "Escalated to L2.", "Replacement part dispatched.", "Customer confirmed it works now.",
               "Waiting for the customer to share photos.", "Closing as resolved.", "Scheduled a technician visit."]
    return lambda r, g: f"{g.pick(openers)} {g.pick(issues)}. {g.pick(closers)}"


def lookup(name: str, values: list, extra: dict[str, list] | None = None, comment: str | None = None) -> Table:
    """A small lookup table with a code and a label (and optional extra columns)."""
    extra = extra or {}
    rows = []
    for i, v in enumerate(values):
        label, code_ = (v if isinstance(v, tuple) else (v, v.upper().replace(" ", "_")[:20]))
        row = {"code": code_, "name": label}
        for k, vals in extra.items():
            row[k] = vals[i]
        rows.append(row)
    cols = [col("code", S(30)), col("name", S(80))]
    for k, vals in extra.items():
        typ = B if isinstance(vals[0], bool) else I if isinstance(vals[0], int) else N if isinstance(vals[0], float) else S(80)
        cols.append(col(k, typ))
    return Table(name, len(rows), cols, fixed=rows, comment=comment)


def draw(table: str, eligible):
    """A parent's children each take a different row of `table` (one payslip per employee per run):
    the eligible rows for this parent are shuffled once and handed out in turn."""
    def gen(r, g):
        p = r["@parent"]
        key = f"_pool_{table}"
        if key not in p:
            pool = [x for x in g.rows[table] if eligible(x, p)]
            g.rnd.shuffle(pool)
            p[key] = pool
        return p[key].pop()[f"{table}_id"] if p[key] else None
    return gen


def pool_size(table: str, eligible, share: float = 1.0):
    def count(p, g):
        key = f"_pool_{table}"
        if key not in p:
            pool = [x for x in g.rows[table] if eligible(x, p)]
            g.rnd.shuffle(pool)
            p[key] = pool
        return int(len(p[key]) * share)
    return count


def qty_for(price_inr_path: str, median_line_inr: float = 250000, sigma: float = 1.3):
    """A line quantity that fits the product: a line is worth about a few lakh rupees (log-normal),
    so cheap meters come by the thousand and DC fast chargers one or two at a time."""
    import math
    def gen(r, g):
        price = float(get(r, price_inr_path) or 1)
        target = math.exp(g.rnd.gauss(math.log(median_line_inr), sigma))
        q = max(1, round(target / price))
        if q > 20:
            q = round(q, -1) if q < 1000 else round(q, -2)
        return float(q)
    return gen
