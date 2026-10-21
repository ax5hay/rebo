"""Fill a structure-only MySQL database with realistic synthetic rows.

Inputs: a database that already has the tables (load schema.sql first) and the
profile.json written by tools/snapshot. No source rows are needed or read.

What makes the data realistic without copying anything:
  * row counts follow the source profile (capped by --cap, scaled by --scale)
  * categorical columns draw from the source's value catalog with the source's frequencies
  * null rates, numeric/date ranges and text lengths follow the source statistics
  * declared foreign keys and measured undeclared references point at generated parents,
    so every join that works on the source also works here
  * personal columns (names, emails, phones, addresses) come from Faker, never the source
  * dates within a row keep their natural order (born < created < started < ended < touched), from
    the spec in tools/synth/correlations/<profile folder>.json (derive.py writes it; B-042)

    uv run --extra synth python tools/synth/synth.py \
        --url mysql+pymysql://root:root@127.0.0.1:3307/jms --profile fixtures/jms_staging/profile.json

Deterministic for a given --seed. See docs/11-local-db-and-synthetic-data.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
import uuid
from collections import defaultdict
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql
from faker import Faker

_INT = {"tinyint", "smallint", "mediumint", "int", "bigint", "year"}
_FLOAT = {"decimal", "float", "double"}
_DATE = {"date", "datetime", "timestamp"}
_TEXT = {"text", "mediumtext", "longtext", "tinytext"}
_INT_MAX = {"tinyint": 127, "smallint": 32767, "mediumint": 8388607, "int": 2147483647, "bigint": 2**62}


def connect(url: str):
    u = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    return pymysql.connect(host=u.hostname, port=u.port or 3306, user=unquote(u.username or ""),
                           password=unquote(u.password or ""), database=u.path.lstrip("/"),
                           charset="utf8mb4", autocommit=False, cursorclass=pymysql.cursors.DictCursor)


def structure(cur, db: str) -> dict:
    cur.execute("""SELECT table_name AS t, column_name AS c, data_type AS dt, column_type AS ct,
                          is_nullable AS nul, column_key AS k, extra AS ex, character_maximum_length AS len,
                          numeric_precision AS np, numeric_scale AS ns
                   FROM information_schema.columns c JOIN information_schema.tables USING (table_schema, table_name)
                   WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name, ordinal_position""", (db,))
    tables: dict[str, dict] = defaultdict(lambda: {"columns": [], "pk": [], "fks": [], "uniques": []})
    for r in cur.fetchall():
        tables[r["t"]]["columns"].append(r)
        if r["k"] == "PRI":
            tables[r["t"]]["pk"].append(r["c"])
    cur.execute("""SELECT table_name AS t, constraint_name AS n, column_name AS c, referenced_table_name AS rt,
                          referenced_column_name AS rc FROM information_schema.key_column_usage
                   WHERE table_schema=%s AND referenced_table_name IS NOT NULL
                   ORDER BY table_name, constraint_name, ordinal_position""", (db,))
    fks: dict[tuple, dict] = {}
    for r in cur.fetchall():
        fk = fks.setdefault((r["t"], r["n"]), {"cols": [], "ref_table": r["rt"], "ref_cols": []})
        fk["cols"].append(r["c"]); fk["ref_cols"].append(r["rc"])
    for (t, _), fk in fks.items():
        tables[t]["fks"].append(fk)
    cur.execute("""SELECT table_name AS t, index_name AS n, column_name AS c FROM information_schema.statistics
                   WHERE table_schema=%s AND non_unique=0 AND index_name <> 'PRIMARY'
                   ORDER BY table_name, index_name, seq_in_index""", (db,))
    uniq: dict[tuple, list] = defaultdict(list)
    for r in cur.fetchall():
        uniq[(r["t"], r["n"])].append(r["c"])
    for (t, _), cols in uniq.items():
        tables[t]["uniques"].append(cols)
    return dict(tables)


class Generator:
    def __init__(self, tables: dict, profile: dict, *, cap: int, scale: float, min_rows: int, seed: int,
                 correlations: dict | None = None):
        self.t, self.p = tables, profile.get("tables", {})
        self.date_order = (correlations or {}).get("tables", {})
        self.rng = random.Random(seed)
        self.fake = Faker("en_US")
        Faker.seed(seed)
        # Undeclared references measured on the source. Only name-backed matches are trusted:
        # value-overlap-only matches between small dense id ranges are often coincidental.
        self.implicit = {(r["table"], r["column"]): (r["ref_table"], r["ref_column"])
                         for r in profile.get("implicit_refs", [])
                         if r["ref_table"] in tables and r.get("by_name")
                         and (r["ref_table"] != r["table"] or r["column"].startswith("parent"))}
        self.n = {}
        for name in tables:
            src = (self.p.get(name) or {}).get("rows") or 0
            self.n[name] = min(cap, round(src * scale)) if src else min_rows
        for name, info in tables.items():  # a parent of a NOT NULL reference needs at least one row
            for fk in info["fks"]:
                cols = {c["c"]: c for c in info["columns"]}
                if self.n[name] and any(cols[c]["nul"] == "NO" for c in fk["cols"]) and fk["ref_table"] in self.n:
                    self.n[fk["ref_table"]] = max(self.n[fk["ref_table"]], 1)
        self.rows: dict[str, list[dict]] = {}
        self.keys: dict[str, list] = {}
        for name, info in tables.items():  # integer single-column keys are known before any row exists
            if len(info["pk"]) == 1:
                col = next(c for c in info["columns"] if c["c"] == info["pk"][0])
                if col["dt"] in _INT:
                    self.keys[name] = list(range(1, self.n[name] + 1))

    # ---- value generation --------------------------------------------------------------------
    def _stats(self, table: str, col: str) -> dict:
        for c in (self.p.get(table) or {}).get("columns", []):
            if c["name"] == col:
                return c
        return {}

    def _date(self, s: dict, kind: str):
        def parse(v):
            try:
                return dt.datetime.fromisoformat(str(v))
            except ValueError:
                return None
        lo = parse(s.get("min")) or dt.datetime(2022, 1, 1)
        hi = parse(s.get("max")) or dt.datetime(2026, 10, 1)
        lo, hi = max(lo, dt.datetime(1970, 1, 2)), min(hi, dt.datetime(2037, 12, 31))
        if hi <= lo:
            hi = lo + dt.timedelta(days=365)
        v = lo + dt.timedelta(seconds=self.rng.randint(0, int((hi - lo).total_seconds())))
        return v.date() if kind == "date" else v.replace(microsecond=0)

    def _text(self, col: dict, s: dict) -> str:
        name, n = col["c"].lower(), col["len"] or 255
        f = self.fake
        if "email" in name: v = f.email()
        elif "first" in name and "name" in name: v = f.first_name()
        elif ("last" in name or "sur" in name) and "name" in name: v = f.last_name()
        elif "phone" in name or "mobile" in name or name.endswith("fax"): v = f.numerify("(###) ###-####")
        elif "zip" in name or "postal" in name: v = f.postcode()
        elif name in ("state", "state_code") or name.endswith("_state"): v = f.state_abbr()
        elif "city" in name: v = f.city()
        elif "country" in name: v = "US"
        elif "address" in name or "street" in name: v = f.street_address()
        elif "url" in name or "link" in name or "website" in name: v = f.url()
        elif "color" in name: v = f.hex_color()
        elif "uuid" in name or "guid" in name: v = str(uuid.UUID(int=self.rng.getrandbits(128)))
        elif "ssn" in name or "social" in name: v = f.ssn()
        elif name.endswith("name") or name == "name": v = f.name() if "agency" not in name else f.company()
        elif "title" in name or "subject" in name: v = f.sentence(nb_words=4).rstrip(".")
        elif col["dt"] in _TEXT or (s.get("avglen") or 0) > 40:
            v = f.text(max_nb_chars=max(20, min(int(s.get("avglen") or 120) * 2, 2000)))
        else:
            v = f.word()
        return v[:n]

    def value(self, table: str, col: dict, i: int):
        name, kind = col["c"], col["dt"]
        if "GENERATED" in (col["ex"] or "").upper():
            return None
        s = self._stats(table, name)
        if col["nul"] == "YES" and self.rng.random() < (s.get("null_rate") or 0):
            return None
        if s.get("values"):
            vals = s["values"]
            return self.rng.choices([v["value"] for v in vals], weights=[v["count"] for v in vals])[0]
        if kind in ("enum", "set"):
            opts = re.findall(r"'((?:[^']|'')*)'", col["ct"])
            return self.rng.choice(opts) if opts else None
        if kind == "bit" or col["ct"].startswith("tinyint(1)"):
            return self.rng.randint(0, 1)
        if kind in _INT:
            lo, hi = s.get("min"), s.get("max")
            lo = int(lo) if isinstance(lo, (int, float)) else 0
            hi = int(hi) if isinstance(hi, (int, float)) else 1000
            unsigned = "unsigned" in col["ct"]
            hi = min(max(hi, lo), _INT_MAX.get(kind, 2**31 - 1))
            lo = max(lo, 0 if unsigned else -hi)
            return self.rng.randint(lo, hi)
        if kind in _FLOAT:
            lo = s.get("min") if isinstance(s.get("min"), (int, float)) else 0
            hi = s.get("max") if isinstance(s.get("max"), (int, float)) else 1000
            return round(self.rng.uniform(lo, max(lo, hi)), col["ns"] or 2)
        if kind in _DATE:
            return self._date(s, kind)
        if kind == "time":
            return f"{self.rng.randint(0, 23):02d}:{self.rng.choice([0, 15, 30, 45]):02d}:00"
        if kind == "json":
            return "{}"
        if kind in ("char", "varchar") or kind in _TEXT:
            return self._text(col, s)
        if col["nul"] == "YES":
            return None
        return b"" if "blob" in kind or "binary" in kind else ""

    def _parent_value(self, ref_table: str, ref_col: str):
        if ref_table in self.keys and self.keys[ref_table] and self.t[ref_table]["pk"] == [ref_col]:
            return self.rng.choice(self.keys[ref_table])
        rows = self.rows.get(ref_table)
        if rows:
            return self.rng.choice(rows)[ref_col]
        return None

    # ---- tables ------------------------------------------------------------------------------
    def order(self) -> list[str]:
        graph = {t: {fk["ref_table"] for fk in info["fks"] if fk["ref_table"] != t and fk["ref_table"] in self.t}
                 for t, info in self.t.items()}
        while True:
            try:
                return list(TopologicalSorter(graph).static_order())
            except CycleError as e:  # drop one edge of the cycle; integer keys are pre-known anyway
                cycle = e.args[1]
                for a, b in zip(cycle, cycle[1:]):
                    if b in graph.get(a, set()):
                        graph[a].discard(b)
                        break
                    if a in graph.get(b, set()):
                        graph[b].discard(a)
                        break
                else:
                    raise

    def table(self, name: str) -> list[dict]:
        info, n = self.t[name], self.n[name]
        cols = info["columns"]
        fk_by_col = {}
        for fk in info["fks"]:
            for c, rc in zip(fk["cols"], fk["ref_cols"]):
                fk_by_col[c] = (fk["ref_table"], rc, fk)
        single_int_pk = name in self.keys
        seen_unique: dict[tuple, set] = defaultdict(set)
        out: list[dict] = []
        attempts = 0
        while len(out) < n and attempts < n * 3:
            attempts += 1
            i = len(out) + 1
            row: dict = {}
            fk_pick: dict[int, dict] = {}
            for c in cols:
                cn = c["c"]
                if single_int_pk and cn == info["pk"][0]:
                    row[cn] = i
                    continue
                if cn in fk_by_col:
                    rt, rc, fk = fk_by_col[cn]
                    s = self._stats(name, cn)
                    if c["nul"] == "YES" and self.rng.random() < (s.get("null_rate") or 0):
                        row[cn] = None
                        continue
                    if len(fk["cols"]) > 1:  # composite: take all columns from one parent row
                        parent = fk_pick.setdefault(id(fk), self.rng.choice(self.rows.get(rt) or [{}]))
                        row[cn] = parent.get(rc)
                    else:
                        row[cn] = self._parent_value(rt, rc)
                    if row[cn] is None and c["nul"] == "NO":
                        row[cn] = self.value(name, c, i)
                    continue
                if (name, cn) in self.implicit:
                    rt, rc = self.implicit[(name, cn)]
                    s = self._stats(name, cn)
                    if c["nul"] == "YES" and self.rng.random() < (s.get("null_rate") or 0):
                        row[cn] = None
                    else:
                        row[cn] = self._parent_value(rt, rc) or self.value(name, c, i)
                    continue
                if "auto_increment" in (c["ex"] or ""):
                    row[cn] = i
                    continue
                row[cn] = self.value(name, c, i)
            self._order_dates(name, row)
            # uniqueness: primary key (if not the simple integer case) and unique indexes
            constraints = [info["pk"]] if info["pk"] and not single_int_pk else []
            constraints += info["uniques"]
            ok = True
            for cs in constraints:
                key = tuple(row.get(c) for c in cs)
                if any(v is None for v in key) and cs != info["pk"]:
                    continue  # NULLs never collide in a unique index
                if key in seen_unique[tuple(cs)]:
                    if len(cs) == 1 and isinstance(row[cs[0]], str):
                        row[cs[0]] = f"{row[cs[0]][: max(1, (self._col(name, cs[0])['len'] or 64) - 8)]}-{i}"
                        key = (row[cs[0]],)
                    elif len(cs) == 1 and isinstance(row[cs[0]], int) and not fk_by_col.get(cs[0]):
                        row[cs[0]] = i
                        key = (i,)
                    else:
                        ok = False
                        break
                seen_unique[tuple(cs)].add(key)
            if ok:
                out.append(row)
        if not single_int_pk and len(info["pk"]) == 1:
            self.keys[name] = [r[info["pk"][0]] for r in out]
        if single_int_pk and len(out) < n:
            self.keys[name] = self.keys[name][: len(out)]
        self.rows[name] = out
        return out

    def _order_dates(self, table: str, row: dict) -> None:
        """Bump any date that falls before a date of a lower tier in the same row (a few hours to 60 days
        later), so e.g. completed >= created always holds."""
        floor = None
        for col, _tier in self.date_order.get(table, []):
            v = row.get(col)
            if v is None:
                continue
            as_dt = v if isinstance(v, dt.datetime) else dt.datetime.combine(v, dt.time())
            if floor and as_dt < floor:
                as_dt = min(floor + dt.timedelta(hours=self.rng.randint(1, 60 * 24)), dt.datetime(2037, 12, 31))
                if not isinstance(v, dt.datetime):  # a DATE is midnight: never the same day as a later floor
                    day = as_dt.date() + dt.timedelta(days=1 if dt.datetime.combine(as_dt.date(), dt.time()) < floor
                                                      else 0)
                    as_dt = dt.datetime.combine(day, dt.time())
                row[col] = as_dt if isinstance(v, dt.datetime) else as_dt.date()
            floor = max(floor or as_dt, as_dt)

    def _col(self, table: str, col: str) -> dict:
        return next(c for c in self.t[table]["columns"] if c["c"] == col)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="mysql+pymysql://root:root@127.0.0.1:3307/jms")
    ap.add_argument("--profile", type=Path, default=Path("fixtures/jms_staging/profile.json"))
    ap.add_argument("--cap", type=int, default=3000, help="max rows per table")
    ap.add_argument("--scale", type=float, default=1.0, help="multiply the source row counts")
    ap.add_argument("--min-rows", type=int, default=0, help="rows for tables empty in the source")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--correlations", type=Path, default=None,
                    help="date-order spec (default: tools/synth/correlations/<profile folder>.json if present)")
    args = ap.parse_args()
    spec_path = args.correlations or Path(__file__).parent / "correlations" / f"{args.profile.parent.name}.json"
    correlations = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.is_file() else None

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    conn = connect(args.url)
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE() AS d")
        db = cur.fetchone()["d"]
        tables = structure(cur, db)
    gen = Generator(tables, profile, cap=args.cap, scale=args.scale, min_rows=args.min_rows, seed=args.seed,
                    correlations=correlations)
    order = gen.order()
    total = 0
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0"); cur.execute("SET UNIQUE_CHECKS=0")
        for t in order:
            cur.execute(f"DELETE FROM `{t}`")
        for k, t in enumerate(order, 1):
            rows = gen.table(t)
            if rows:
                cols = [c["c"] for c in tables[t]["columns"] if "GENERATED" not in (c["ex"] or "").upper()]
                sql = (f"INSERT INTO `{t}` ({', '.join(f'`{c}`' for c in cols)}) "
                       f"VALUES ({', '.join(['%s'] * len(cols))})")
                for b in range(0, len(rows), 1000):
                    cur.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows[b:b + 1000]])
            total += len(rows)
            print(f"[synth] {k}/{len(order)} {t}: {len(rows)} rows", file=sys.stderr)
        cur.execute("SET FOREIGN_KEY_CHECKS=1"); cur.execute("SET UNIQUE_CHECKS=1")
    conn.commit()
    print(json.dumps({"database": db, "tables": len(order), "rows": total, "seed": args.seed, "cap": args.cap}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
