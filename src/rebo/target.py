"""The database being reported on: read-only execution, introspection and profiling.

Dialect-neutral through SQLAlchemy; MySQL/MariaDB, PostgreSQL and SQLite get explicit
read-only session settings. See docs/02-knowledge-bootstrap.md and docs/06-sql-safety.md.
"""
from __future__ import annotations

import datetime as dt
import decimal
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

from .safety import sqlglot_dialect

_TEXTUAL = ("char", "text", "enum", "set", "string", "clob")
_COMPARABLE = ("int", "dec", "num", "float", "double", "real", "date", "time", "year", "money")
_BINARY = ("blob", "binary", "bytea", "geometry", "point", "polygon", "linestring")
# The database role the current person's queries run as (row-level security, docs/06 §RLS). Set per
# request with TargetDB.acting_as; None runs as the configured read-only login.
_ROLE: ContextVar[str | None] = ContextVar("rebo_db_role", default=None)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    truncated: bool
    elapsed_ms: int


def cell(v: Any) -> Any:
    """JSON-safe cell value."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return str(v)
    if isinstance(v, decimal.Decimal):
        return float(v) if v == v.to_integral_value() or abs(v) < 1e15 else str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        b = bytes(v)
        return int.from_bytes(b, "big") if len(b) == 1 else f"<{len(b)} bytes>"
    if isinstance(v, uuid.UUID):
        return str(v)
    return str(v)


class TargetDB:
    def __init__(self, url: str, *, timeout_s: int = 30):
        self.engine: Engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
        self.timeout_s = timeout_s
        self.kind = self.engine.dialect.name
        self.dialect = sqlglot_dialect(self.kind)
        self._q = self.engine.dialect.identifier_preparer.quote

    def quote(self, name: str) -> str:
        return self._q(name)

    # ---- execution -------------------------------------------------------------------
    @contextmanager
    def acting_as(self, role: str | None):
        """Run the queries inside as `role` (PostgreSQL SET LOCAL ROLE), so the database's own
        row-level security policies decide which rows this person sees."""
        if role and self.kind != "postgresql":
            raise RuntimeError("database_role (row-level security) needs PostgreSQL.")
        token = _ROLE.set(role or None)
        try:
            yield
        finally:
            _ROLE.reset(token)

    def _read_only_session(self, cur) -> None:
        ms = self.timeout_s * 1000
        if self.kind in ("mysql", "mariadb"):
            cur.execute("SET SESSION TRANSACTION READ ONLY")
            cur.execute(f"SET SESSION {'max_statement_time' if self.kind == 'mariadb' else 'max_execution_time'}"
                        f"={ms if self.kind == 'mysql' else self.timeout_s}")
        elif self.kind == "postgresql":
            cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            cur.execute("SET TRANSACTION READ ONLY")  # the session default starts with the next transaction
            cur.execute(f"SET statement_timeout = {ms}")
            if role := _ROLE.get():  # LOCAL: undone by the rollback, so a pooled connection never keeps it
                cur.execute(f"SET LOCAL ROLE {self.quote(role)}")
        elif self.kind == "sqlite":
            cur.execute("PRAGMA query_only = ON")

    def run(self, sql: str, *, max_rows: int) -> QueryResult:
        """Run already-guarded SQL. Raw DBAPI cursor so '%' and ':' in literals are never
        treated as bind markers."""
        conn = self.engine.raw_connection()
        started = time.perf_counter()
        try:
            cur = conn.cursor()
            self._read_only_session(cur)
            cur.execute(sql)
            columns = [d[0] for d in (cur.description or [])]
            raw = cur.fetchmany(max_rows + 1)
            cur.close()
        finally:
            try:
                conn.rollback()
            finally:
                conn.close()
        truncated = len(raw) > max_rows
        rows = [[cell(v) for v in r] for r in raw[:max_rows]]
        return QueryResult(columns, rows, truncated, int((time.perf_counter() - started) * 1000))

    # ---- introspection ---------------------------------------------------------------
    def introspect(self, allow: set[str] | None = None) -> dict[str, dict[str, Any]]:
        """{table: {columns: [...], pk: [...], fks: [...], uniques: [...], comment}}"""
        insp = inspect(self.engine)
        out: dict[str, dict[str, Any]] = {}
        for t in sorted(insp.get_table_names()):
            if allow and t not in allow:
                continue
            cols = [{"name": c["name"], "type": str(c["type"]).lower(), "nullable": bool(c.get("nullable", True)),
                     "comment": c.get("comment")} for c in insp.get_columns(t)]
            pk = insp.get_pk_constraint(t).get("constrained_columns") or []
            fks = [{"cols": fk["constrained_columns"], "ref_table": fk["referred_table"],
                    "ref_cols": fk["referred_columns"]} for fk in insp.get_foreign_keys(t)
                   if fk.get("referred_table")]
            try:
                comment = insp.get_table_comment(t).get("text")
            except NotImplementedError:
                comment = None
            out[t] = {"columns": cols, "pk": pk, "fks": fks, "comment": comment}
        return out

    # ---- profiling -------------------------------------------------------------------
    def _scalar_rows(self, sql: str) -> list[tuple]:
        conn = self.engine.raw_connection()
        try:
            cur = conn.cursor()
            self._read_only_session(cur)
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            return rows
        finally:
            conn.rollback()
            conn.close()

    def profile_table(self, table: str, columns: list[dict], *, sample_rows: int = 200_000,
                      value_cap: int = 1000) -> dict[str, Any]:
        """Row count plus per-column null rate, distinct count, min/max, average length and
        top values. Large tables are profiled on their first `sample_rows` rows."""
        q = self.quote
        n = int(self._scalar_rows(f"SELECT COUNT(*) FROM {q(table)}")[0][0])
        src = q(table) if n <= sample_rows else f"(SELECT * FROM {q(table)} LIMIT {sample_rows}) s"
        stats: dict[str, dict[str, Any]] = {c["name"]: {} for c in columns}
        if n:
            parts, keys = [], []
            for c in columns:
                ty, col = c["type"], q(c["name"])
                if any(b in ty for b in _BINARY):
                    continue
                parts.append(f"SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)"); keys.append((c["name"], "nulls"))
                if "json" in ty or "clob" in ty:
                    parts.append(f"AVG({self._len(col)})"); keys.append((c["name"], "avglen"))
                    continue
                # TEXT is the ordinary string type in SQLite/Postgres, so strings are profiled alike
                # and "free text" is decided later by measured average length, not by type name.
                parts.append(f"COUNT(DISTINCT {col})"); keys.append((c["name"], "distinct"))
                if any(t in ty for t in _TEXTUAL):
                    parts.append(f"AVG({self._len(col)})"); keys.append((c["name"], "avglen"))
                elif any(t in ty for t in _COMPARABLE):
                    parts.append(f"MIN({col})"); keys.append((c["name"], "min"))
                    parts.append(f"MAX({col})"); keys.append((c["name"], "max"))
            if parts:
                row = self._scalar_rows(f"SELECT {', '.join(parts)} FROM {src}")[0]
                denom = min(n, sample_rows)
                for (name, key), v in zip(keys, row):
                    if v is None:
                        continue
                    if key == "nulls":
                        stats[name]["null_rate"] = round(float(v) / denom, 4)
                    elif key == "avglen":
                        stats[name]["avglen"] = round(float(v), 1)
                    else:
                        stats[name][key] = cell(v)
        top: dict[str, list[dict[str, Any]]] = {}
        for c in columns:
            s = stats[c["name"]]
            d = s.get("distinct") or 0
            textual = any(t in c["type"] for t in _TEXTUAL) and (s.get("avglen") or 0) <= 60
            small_int = "int" in c["type"] and d <= 50
            if n and d and ((textual and d <= value_cap) or small_int):
                col = q(c["name"])
                rows = self._scalar_rows(f"SELECT {col}, COUNT(*) FROM {src} WHERE {col} IS NOT NULL "
                                         f"GROUP BY {col} ORDER BY COUNT(*) DESC LIMIT {value_cap}")
                top[c["name"]] = [{"value": cell(v), "count": int(k)} for v, k in rows]
        return {"rows": n, "stats": stats, "top_values": top}

    def _len(self, col: str) -> str:
        return f"LENGTH({col})" if self.kind == "sqlite" else f"CHAR_LENGTH({col})"

    def containment(self, child: str, child_col: str, parent: str, parent_col: str, sample: int = 500) -> float:
        """Share of sampled distinct child values that exist in the parent column (join inference)."""
        q = self.quote
        sql = (f"SELECT COUNT(*), SUM(CASE WHEN p.v IS NOT NULL THEN 1 ELSE 0 END) FROM "
               f"(SELECT DISTINCT {q(child_col)} AS v FROM {q(child)} WHERE {q(child_col)} IS NOT NULL LIMIT {sample}) c "
               f"LEFT JOIN (SELECT DISTINCT {q(parent_col)} AS v FROM {q(parent)}) p ON p.v = c.v")
        total, hit = self._scalar_rows(sql)[0]
        return float(hit or 0) / float(total) if total else 0.0
