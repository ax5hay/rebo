"""A small declarative generator for a large, coherent, synthetic company database.

A table is a list of columns; each column has a SQL type and a generator `gen(r, g)` that sees the row
built so far (`r`) and the generator context (`g`: seeded randomness, Faker per locale, references to
rows already generated). Foreign keys pick a parent row; the parent row is then available to later
columns as `r["@<column>"]`, so a child's dates, currency or country follow its parent's.

`per=(parent, lo, hi)` makes a child table by giving each parent row lo..hi children (order lines,
payslip lines), instead of a fixed count. Rows of tables that nothing references are written and
dropped, so memory holds only parents. Totals that depend on children are filled afterwards with
portable correlated UPDATEs (`post`).
"""
from __future__ import annotations

import bisect
import datetime as dt
import itertools
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from faker import Faker
from sqlalchemy import (BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, MetaData, Numeric,
                        String, Table as SATable, Text, create_engine, text)

# column types
I, BI, N, N4, B, D, TS, TX = "int", "bigint", "num", "num4", "bool", "date", "ts", "text"
S = lambda n=120: f"str{n}"  # noqa: E731

START, END = dt.date(2021, 4, 1), dt.date(2026, 10, 20)   # five and a half Indian fiscal years
NOW = dt.datetime(2026, 10, 21, 18, 0)

# Where the people and companies come from: an Indian company with foreign subsidiaries and customers.
LOCALES = {"IN": "en_IN", "GB": "en_GB", "US": "en_US", "DE": "de_DE", "FR": "fr_FR", "NL": "nl_NL",
           "AU": "en_AU", "SG": "en_US", "AE": "en_US", "JP": "en_US", "ES": "es_ES", "IE": "en_IE"}
COUNTRY_MIX = [("IN", 58), ("GB", 9), ("US", 9), ("DE", 6), ("SG", 4), ("AE", 4), ("FR", 3), ("NL", 2),
               ("AU", 2), ("ES", 1), ("IE", 1), ("JP", 1)]
CURRENCY = {"IN": "INR", "GB": "GBP", "US": "USD", "DE": "EUR", "FR": "EUR", "NL": "EUR", "ES": "EUR", "IE": "EUR",
            "AU": "AUD", "SG": "SGD", "AE": "AED", "JP": "JPY"}


def col(name: str, typ: str, gen: Callable | None = None, *, null: float = 0.0, unique: bool = False,
        index: bool = False) -> "Col":
    return Col(name, typ, gen, null=null, unique=unique, index=index)


def fk(name: str, table: str, *, null: float = 0.0, skew: float = 0.0, where: Callable | None = None,
       declare: bool = True, match: tuple[str, str] | None = None, pick: Callable | None = None,
       optional: bool = False) -> "Col":
    """A foreign key to `table`. skew > 0 makes some parents far more popular (big customers, busy
    products); `where(parent, row)` restricts the choice (small tables); `match=(parent column, row
    path)` picks among parents whose column equals the row's value, through an index (large tables:
    the ship-to site of the order's own customer); `pick(r, g)` returns the parent id directly;
    declare=False leaves the constraint out, as legacy schemas often do."""
    return Col(name, I, None, null=null, ref=table, skew=skew, where=where, declare=declare, index=True,
               match=match, pick=pick, optional=optional)


@dataclass
class Col:
    name: str
    typ: str
    gen: Callable | None = None
    null: float = 0.0
    unique: bool = False
    index: bool = False
    ref: str | None = None
    skew: float = 0.0
    where: Callable | None = None
    declare: bool = True
    match: tuple[str, str] | None = None
    pick: Callable | None = None
    optional: bool = False   # NULL allowed although every generated row has a value (cleared later)


@dataclass
class Table:
    name: str
    n: int
    cols: list[Col]
    per: tuple | None = None   # (parent table, min, max) or (parent table, count(parent, g))
    pk: str | None = None
    post: list[str] = field(default_factory=list)  # SQL run after every table is loaded
    comment: str | None = None
    fixed: list[dict] | None = None             # literal rows (lookups), instead of generated ones
    after_load: list[str] = field(default_factory=list)  # SQL run right after this table is loaded
    reload: list[tuple[str, list[str]]] = field(default_factory=list)  # then re-read these columns into memory

    def __post_init__(self):
        self.pk = self.pk or f"{self.name}_id"


class Ctx:
    """What a generator sees: randomness, fakers, references, sequences."""

    def __init__(self, seed: int, scale: float):
        self.rnd = random.Random(seed)
        self.scale = scale
        self.fakers: dict[str, Faker] = {}
        for i, loc in enumerate(sorted(set(LOCALES.values()))):
            f = Faker(loc)
            f.seed_instance(seed + i)
            self.fakers[loc] = f
        self.rows: dict[str, list[dict]] = {}
        self._cum: dict[tuple[str, float], list[float]] = {}
        self._seq = itertools.count(1)

    # ---- randomness ----------------------------------------------------------------------------
    def pick(self, items, weights=None):
        return self.rnd.choices(items, weights=weights, k=1)[0] if weights else self.rnd.choice(items)

    def chance(self, p: float) -> bool:
        return self.rnd.random() < p

    def int(self, lo: int, hi: int) -> int:
        return self.rnd.randint(lo, hi)

    def money(self, lo: float, hi: float, step: float = 1.0, skew: float = 1.0) -> float:
        """lo..hi, by default skewed toward small values (most invoices are small)."""
        x = self.rnd.random() ** skew
        return round(round((lo + (hi - lo) * x) / step) * step, 2)

    def normal(self, mu: float, sigma: float, lo: float | None = None, hi: float | None = None) -> float:
        v = self.rnd.gauss(mu, sigma)
        if lo is not None:
            v = max(lo, v)
        if hi is not None:
            v = min(hi, v)
        return v

    def faker(self, country: str = "IN") -> Faker:
        return self.fakers[LOCALES.get(country, "en_US")]

    def country(self) -> str:
        return self.pick([c for c, _ in COUNTRY_MIX], [w for _, w in COUNTRY_MIX])

    # ---- dates: business grows over time, with a festive-season bump (Oct-Nov) and FY-end push (Mar)
    def date(self, start: dt.date = START, end: dt.date = END, growth: float = 1.6) -> dt.date:
        span = (end - start).days
        while True:
            t = self.rnd.random() ** (1 / growth)   # more recent dates are likelier
            d = start + dt.timedelta(days=int(t * span))
            w = 1.35 if d.month in (10, 11, 3) else 0.85 if d.month in (5, 6) else 1.0
            if d.weekday() >= 5:
                w *= 0.35
            if self.rnd.random() < w / 1.35:
                return d

    def after(self, d: dt.date | dt.datetime | None, lo: int, hi: int) -> dt.date | None:
        if d is None:
            return None
        if isinstance(d, dt.datetime):
            d = d.date()
        out = d + dt.timedelta(days=self.int(lo, hi))
        return out if out <= END else None

    def ts(self, d: dt.date | None, start_h: int = 8, end_h: int = 19) -> dt.datetime | None:
        if d is None:
            return None
        return dt.datetime(d.year, d.month, d.day, self.int(start_h, end_h - 1), self.int(0, 59), self.int(0, 59))

    def code(self, prefix: str, n: int, width: int = 6) -> str:
        return f"{prefix}-{n:0{width}d}"

    # ---- references --------------------------------------------------------------------------
    def by_id(self, table: str, pid: int | None) -> dict | None:
        rows = self.rows.get(table) or []
        return rows[pid - 1] if pid and 0 < pid <= len(rows) else None

    def matching(self, table: str, key: str, value) -> list[dict]:
        idx = self.__dict__.setdefault("_idx", {})
        if (table, key) not in idx:
            m: dict = {}
            for row in self.rows.get(table) or []:
                m.setdefault(row.get(key), []).append(row)
            idx[(table, key)] = m
        return idx[(table, key)].get(value, [])

    def ref(self, table: str, skew: float = 0.0, where: Callable | None = None, r: dict | None = None) -> dict | None:
        rows = self.rows.get(table) or []
        if not rows:
            return None
        if where is not None:
            for _ in range(40):
                p = self._pick_row(table, rows, skew)
                if where(p, r or {}):
                    return p
            cand = [p for p in rows if where(p, r or {})]
            return self.rnd.choice(cand) if cand else None
        return self._pick_row(table, rows, skew)

    def _pick_row(self, table: str, rows: list[dict], skew: float) -> dict:
        if not skew:
            return self.rnd.choice(rows)
        key = (table, skew)
        cum = self._cum.get(key)
        if cum is None or len(cum) != len(rows):
            ws = [1 / (i + 1) ** skew for i in range(len(rows))]   # Zipf-like popularity
            cum = list(itertools.accumulate(ws))
            self._cum[key] = cum
        return rows[bisect.bisect_left(cum, self.rnd.random() * cum[-1])]


def _sa_type(t: str):
    if t == I:
        return Integer()
    if t == BI:
        return BigInteger()
    if t == N:
        return Numeric(14, 2)
    if t == N4:
        return Numeric(12, 4)
    if t == B:
        return Boolean()
    if t == D:
        return Date()
    if t == TS:
        return DateTime()
    if t == TX:
        return Text()
    if t.startswith("str"):
        return String(int(t[3:]))
    raise ValueError(t)


def build(tables: list[Table], url: str, *, seed: int = 7, scale: float = 1.0, echo: Callable[[str], None] = print,
          drop: bool = True) -> dict[str, int]:
    """Create every table on `url`, generate and load the rows, then run the post-load updates."""
    names = {t.name for t in tables}
    assert len(names) == len(tables), "duplicate table names"
    referenced = {c.ref for t in tables for c in t.cols if c.ref} | {t.per[0] for t in tables if t.per}
    for t in tables:
        for c in t.cols:
            assert not c.ref or c.ref in names, f"{t.name}.{c.name} -> unknown {c.ref}"
    engine = create_engine(url)
    md = MetaData()
    sa: dict[str, SATable] = {}
    for t in tables:
        cols = [Column(t.pk, Integer, primary_key=True, autoincrement=False)]
        for c in t.cols:
            if c.name.startswith("_"):  # helper values (a row's country, ...) that children read, not stored
                continue
            args = [ForeignKey(f"{c.ref}.{c.ref}_id")] if c.ref and c.declare else []
            cols.append(Column(c.name, _sa_type(c.typ), *args, nullable=not (c.ref and not c.null and not c.optional), unique=c.unique))
        sa[t.name] = SATable(t.name, md, *cols, comment=t.comment)
        for c in t.cols:
            if c.index and not c.unique and not c.name.startswith("_"):
                Index(f"ix_{t.name}_{c.name}"[:63], sa[t.name].c[c.name])
    if drop:
        md.drop_all(engine)
    md.create_all(engine)
    g = Ctx(seed, scale)
    counts: dict[str, int] = {}
    for t in tables:
        rows = list(_rows(t, g, scale))
        store = [{k: v for k, v in r.items() if not k.startswith(("@", "_"))} for r in rows]
        limits = {c.name: int(c.typ[3:]) for c in t.cols if c.typ.startswith("str") and not c.name.startswith("_")}
        for row in store:  # SQLite does not enforce VARCHAR lengths; PostgreSQL does: check here for both
            for k, n in limits.items():
                v = row.get(k)
                if isinstance(v, str) and len(v) > n:
                    raise ValueError(f"{t.name}.{k} is VARCHAR({n}) but got {len(v)} characters: {v!r}")
        with engine.begin() as conn:
            for i in range(0, len(store), 5000):
                conn.execute(sa[t.name].insert(), store[i:i + 5000])
        counts[t.name] = len(store)
        if t.name in referenced:
            g.rows[t.name] = [{k: v for k, v in r.items() if not k.startswith("@")} for r in rows]
        if t.after_load:
            with engine.begin() as conn:
                for sql in t.after_load:
                    conn.execute(text(sql))
        for table, cols in t.reload:  # values computed in SQL (totals) become visible to later tables
            pk = f"{table}_id"
            with engine.connect() as conn:
                got = conn.execute(text(f"SELECT {pk}, {', '.join(cols)} FROM {table}")).all()
            for row in got:
                target = g.by_id(table, row[0])
                if target is not None:
                    target.update(zip(cols, row[1:]))
        echo(f"{t.name}: {len(store):,}")
    with engine.begin() as conn:
        for t in tables:
            for sql in t.post:
                conn.execute(text(sql))
    engine.dispose()
    return counts


def _rows(t: Table, g: Ctx, scale: float):
    if t.fixed is not None:
        for i, row in enumerate(t.fixed, 1):
            yield {t.pk: i, **row}
        return
    if t.per:
        parent = t.per[0]
        count = t.per[1] if callable(t.per[1]) else (lambda p, g, lo=t.per[1], hi=t.per[2]: g.int(lo, hi))
        parents = g.rows.get(parent) or []
        n = 0
        for p in parents:
            for _ in range(count(p, g)):
                n += 1
                yield _row(t, g, n, p)
        return
    for i in range(1, max(1, round(t.n * scale)) + 1):
        yield _row(t, g, i, None)


def _row(t: Table, g: Ctx, i: int, parent: dict | None) -> dict:
    r: dict[str, Any] = {t.pk: i, "_i": i}
    if parent is not None:
        r["@parent"] = parent
    for c in t.cols:
        if c.ref:
            if parent is not None and c.ref == t.per[0] and f"@{c.name}" not in r and c.name == f"{t.per[0]}_id":
                p = parent
            elif c.null and g.chance(c.null):
                p = None
            elif c.pick:
                p = g.by_id(c.ref, c.pick(r, g))
            elif c.match:
                cands = g.matching(c.ref, c.match[0], _path(r, c.match[1]))
                p = g.rnd.choice(cands) if cands else (None if c.null else g.ref(c.ref))
            else:
                p = g.ref(c.ref, c.skew, c.where, r)
            r[f"@{c.name}"] = p
            r[c.name] = p[f"{c.ref}_id"] if p else None
            continue
        v = c.gen(r, g) if c.gen else None
        if c.null and v is not None and g.chance(c.null):
            v = None
        r[c.name] = v
    return r


def _path(r: dict, path: str):
    cur = r
    for part in path.split("."):
        if cur is None:
            return None
        cur = cur.get(part)
    return cur
