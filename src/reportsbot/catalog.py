"""Catalog: learn the target database's structure and contents with no hand-written config.

`bootstrap()` = introspect -> profile -> detect protected columns -> infer joins ->
index schema docs and values -> (optional) embed -> (optional) LLM-drafted descriptions.
`Catalog` is the read side the agent tools use. See docs/02-knowledge-bootstrap.md.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .retrieval import Index, split_identifier
from .store import Store, now
from .target import TargetDB

log = logging.getLogger(__name__)

# Column names that hold credentials or regulated identifiers. Values are never read back
# into prompts and the guard refuses any query that touches them.
_SECRET_NAME = re.compile(
    r"(passw|secret|token|api_?key|private_?key|ssn|social_security|tax_?id|encrypt|cipher|"
    r"hash|salt|otp|mfa|cvv|card_?num|iban|routing_?num|account_?num|session_?key|credential)",
    re.I)
# Values that look like ciphertext or password hashes (Fernet, bcrypt, argon2, PGP, long base64).
_SECRET_VALUE = re.compile(r"^(gAAAA[\w-]{20,}|\$2[aby]\$|\$argon2|-----BEGIN|[A-Za-z0-9+/=_-]{60,}$)")
_IDISH = re.compile(r"(.+?)_?id$", re.I)
_TEXTUAL = ("char", "text", "enum", "set", "string")


def fingerprint(columns: list[dict]) -> str:
    sig = "|".join(f"{c['name']}:{c['type']}" for c in sorted(columns, key=lambda c: c["name"]))
    return hashlib.sha256(sig.encode()).hexdigest()[:16]


def _table_doc(table: str, info: dict, description: str | None) -> str:
    cols = " ".join(split_identifier(c["name"]) for c in info["columns"])
    return " . ".join(x for x in [split_identifier(table), info.get("comment") or "", description or "", cols] if x)


def _column_doc(table: str, col: dict, top: list[dict] | None, description: str | None) -> str:
    vals = ", ".join(str(v["value"]) for v in (top or [])[:12] if isinstance(v["value"], str))
    parts = [split_identifier(table), split_identifier(col["name"]), col.get("comment") or "",
             description or "", f"values: {vals}" if vals else ""]
    return " . ".join(p for p in parts if p)


def bootstrap(target: TargetDB, store: Store, index: Index, *, allow: set[str] | None = None,
              deny_columns: str = "", describe: Callable[[dict[str, Any]], dict] | None = None,
              workers: int = 4, progress: Callable[[str], None] = print) -> dict[str, int]:
    deny = re.compile(deny_columns, re.I) if deny_columns else None
    progress(f"introspecting {target.kind} database ...")
    meta = target.introspect(allow)
    progress(f"{len(meta)} tables; profiling ...")

    def prof(t: str) -> tuple[str, dict]:
        try:
            return t, target.profile_table(t, meta[t]["columns"])
        except Exception as e:  # one unreadable table must not stop the bootstrap
            log.warning("profile %s failed: %s", t, e)
            return t, {"rows": None, "stats": {}, "top_values": {}, "error": str(e)}

    profiles: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (t, p) in enumerate(pool.map(prof, meta), 1):
            profiles[t] = p
            if i % 25 == 0 or i == len(meta):
                progress(f"  profiled {i}/{len(meta)}")

    progress("detecting protected columns ...")
    sensitive: set[tuple[str, str]] = set()
    for t, info in meta.items():
        textual = [c["name"] for c in info["columns"] if any(x in c["type"] for x in _TEXTUAL)]
        samples: dict[str, list] = {}
        if textual and profiles[t].get("rows"):
            try:
                cols = ", ".join(target.quote(c) for c in textual)
                res = target.run(f"SELECT {cols} FROM {target.quote(t)} LIMIT 25", max_rows=25)
                samples = {c: [r[i] for r in res.rows if r[i]] for i, c in enumerate(res.columns)}
            except Exception as e:
                log.warning("sample %s failed: %s", t, e)
        for c in info["columns"]:
            vals = [str(v) for v in samples.get(c["name"], [])]
            looks_secret = bool(vals) and sum(bool(_SECRET_VALUE.match(v)) for v in vals) >= max(1, len(vals) // 2)
            if _SECRET_NAME.search(c["name"]) or looks_secret or (deny and deny.search(f"{t}.{c['name']}")):
                sensitive.add((t, c["name"]))

    # Drafted descriptions survive re-bootstraps while a table's shape is unchanged, with or without --describe.
    descriptions: dict[str, dict] = {}
    old = {r["name"]: r for r in store.all("SELECT name, fingerprint, description FROM cat_table")}
    old_cols = {(r["table_name"], r["name"]): r["description"]
                for r in store.all("SELECT table_name, name, description FROM cat_column")}
    todo = []
    for t, info in meta.items():
        if (t in old and old[t]["fingerprint"] == fingerprint(info["columns"])
                and len((old[t]["description"] or "").split()) >= 6):
            descriptions[t] = {"table": old[t]["description"],
                               "columns": {c["name"]: old_cols.get((t, c["name"])) for c in info["columns"]}}
        else:
            todo.append(t)
    if describe and todo:
        progress("drafting descriptions with the LLM (trust: draft) ...")

        def desc(t: str) -> tuple[str, dict]:
            payload = {"table": t, "rows": profiles[t].get("rows"), "comment": meta[t].get("comment"),
                       "foreign_keys": meta[t]["fks"],
                       "columns": [{"name": c["name"], "type": c["type"], **profiles[t]["stats"].get(c["name"], {}),
                                    "sample_values": [] if (t, c["name"]) in sensitive else
                                    [v["value"] for v in profiles[t]["top_values"].get(c["name"], [])[:8]]}
                                   for c in meta[t]["columns"]]}
            try:
                return t, describe(payload)
            except Exception as e:
                log.warning("describe %s failed: %s", t, e)
                return t, {}

        with ThreadPoolExecutor(max_workers=8) as pool:
            for i, (t, d) in enumerate(pool.map(desc, todo), 1):
                descriptions[t] = d
                if i % 25 == 0 or i == len(todo):
                    progress(f"  described {i}/{len(todo)} (reused {len(meta) - len(todo)})")

    progress("writing catalog ...")
    with store.tx() as db:
        db.execute("DELETE FROM cat_column"); db.execute("DELETE FROM cat_table")
        db.execute("DELETE FROM cat_join WHERE source != 'learned'")
        db.execute("DELETE FROM schema_fts"); db.execute("DELETE FROM value_fts")
        for t, info in meta.items():
            p, d = profiles[t], descriptions.get(t, {})
            db.execute("INSERT INTO cat_table(name, rows, comment, description, fingerprint, profiled_at) "
                       "VALUES(?,?,?,?,?,?)", (t, p.get("rows"), info.get("comment"), d.get("table"),
                                               fingerprint(info["columns"]), now()))
            db.execute("INSERT INTO schema_fts(kind, table_name, column_name, text) VALUES('table',?,?,?)",
                       (t, "", _table_doc(t, info, d.get("table"))))
            for pos, c in enumerate(info["columns"]):
                is_secret = (t, c["name"]) in sensitive
                top = None if is_secret else p["top_values"].get(c["name"])
                cdesc = (d.get("columns") or {}).get(c["name"])
                db.execute("INSERT INTO cat_column(table_name, name, type, nullable, is_pk, comment, description, "
                           "sensitive, stats, top_values, pos) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                           (t, c["name"], c["type"], int(c["nullable"]), int(c["name"] in info["pk"]),
                            c.get("comment"), cdesc, int(is_secret), json.dumps(p["stats"].get(c["name"], {})),
                            json.dumps(top) if top else None, pos))
                db.execute("INSERT INTO schema_fts(kind, table_name, column_name, text) VALUES('column',?,?,?)",
                           (t, c["name"], _column_doc(t, c, top, cdesc)))
                if top and any(x in c["type"] for x in _TEXTUAL):
                    db.executemany("INSERT INTO value_fts(value, table_name, column_name, freq) VALUES(?,?,?,?)",
                                   [(str(v["value"]), t, c["name"], v["count"]) for v in top
                                    if isinstance(v["value"], str) and 0 < len(v["value"]) <= 80])
            for fk in info["fks"]:
                db.execute("INSERT INTO cat_join VALUES(?,?,?,?, 'fk', 1.0) ON CONFLICT(from_table, from_cols, "
                           "to_table, to_cols) DO UPDATE SET source=excluded.source, confidence=excluded.confidence",
                           (t, ",".join(fk["cols"]), fk["ref_table"], ",".join(fk["ref_cols"])))

    progress("inferring undeclared joins ...")
    inferred = _infer_joins(target, store, meta, profiles)

    if index.embedder.available:
        progress("embedding schema docs (local, CPU) ...")
        refs, texts = [], []
        for r in store.all("SELECT table_name, column_name, text FROM schema_fts"):
            refs.append(f"schema:{r['table_name']}.{r['column_name'] or ''}")
            texts.append(r["text"][:1000])
        index.drop_vectors("schema:")
        index.put_vectors(refs, texts)

    store.meta_set("bootstrapped_at", now())
    store.meta_set("dialect", target.dialect)
    counts = {"tables": len(meta), "columns": sum(len(m["columns"]) for m in meta.values()),
              "foreign_keys": sum(len(m["fks"]) for m in meta.values()), "inferred_joins": inferred,
              "protected_columns": len(sensitive),
              "indexed_values": store.one("SELECT COUNT(*) AS n FROM value_fts")["n"],
              "described_tables": sum(1 for d in descriptions.values() if d.get("table"))}
    progress(json.dumps(counts))
    return counts


def _infer_joins(target: TargetDB, store: Store, meta: dict, profiles: dict) -> int:
    """Propose joins the schema does not declare: `<x>_id` columns whose values sit inside
    another table's single-column primary key (>= 90% of sampled distinct values)."""
    declared = {(r["from_table"], r["from_cols"]) for r in store.all("SELECT from_table, from_cols FROM cat_join")}
    pk_owner: dict[str, list[str]] = {}
    for t, info in meta.items():
        if len(info["pk"]) == 1:
            pk_owner.setdefault(info["pk"][0].lower(), []).append(t)
    tables_lower = {t.lower(): t for t in meta}
    found = 0
    for t, info in meta.items():
        for c in info["columns"]:
            name = c["name"]
            if (t, name) in declared or [name] == info["pk"] or "int" not in c["type"] and "char" not in c["type"]:
                continue
            m = _IDISH.match(name)
            if not m:
                continue
            stem = m.group(1).lower().rstrip("_")
            cands = [x for x in pk_owner.get(name.lower(), []) if x != t]
            for guess in (stem, stem + "s", stem.removesuffix("s")):
                if guess in tables_lower and tables_lower[guess] != t and len(meta[tables_lower[guess]]["pk"]) == 1:
                    cands.append(tables_lower[guess])
            if (profiles[t]["stats"].get(name, {}).get("distinct") or 0) < 3:
                continue
            best: tuple[float, int, str, str] | None = None
            for rank, parent in enumerate(list(dict.fromkeys(cands))[:3]):
                pcol = meta[parent]["pk"][0]
                try:
                    share = target.containment(t, name, parent, pcol)
                except Exception:
                    continue
                # a column references one table: keep the best share, same-name keys first on ties
                if share >= 0.9 and (best is None or (share, -rank) > (best[0], -best[1])):
                    best = (share, rank, parent, pcol)
            if best:
                with store.tx() as db:
                    db.execute("INSERT INTO cat_join VALUES(?,?,?,?, 'inferred', ?) ON CONFLICT DO NOTHING",
                               (t, name, best[2], best[3], round(0.9 * best[0], 3)))
                found += 1
    return found


class Catalog:
    """Read side used by the agent tools and the guard."""

    def __init__(self, store: Store):
        self.store = store
        self._schema: dict[str, dict[str, str]] | None = None
        self._sensitive: set[tuple[str, str]] | None = None
        self._pks: dict[str, list[str]] | None = None

    def refresh(self) -> None:
        self._schema = self._sensitive = self._pks = None

    @property
    def schema(self) -> dict[str, dict[str, str]]:
        if self._schema is None:
            s: dict[str, dict[str, str]] = {}
            for r in self.store.all("SELECT table_name, name, type FROM cat_column"):
                s.setdefault(r["table_name"], {})[r["name"]] = r["type"]
            self._schema = s
        return self._schema

    @property
    def sensitive(self) -> set[tuple[str, str]]:
        if self._sensitive is None:
            self._sensitive = {(r["table_name"], r["name"]) for r in
                               self.store.all("SELECT table_name, name FROM cat_column WHERE sensitive=1")}
        return self._sensitive

    @property
    def primary_keys(self) -> dict[str, list[str]]:
        """{table: [pk columns]}; tables without a declared primary key are absent."""
        if self._pks is None:
            pks: dict[str, list[str]] = {}
            for r in self.store.all("SELECT table_name, name FROM cat_column WHERE is_pk=1 ORDER BY table_name, pos"):
                pks.setdefault(r["table_name"], []).append(r["name"])
            self._pks = pks
        return self._pks

    def fingerprints(self, tables: list[str]) -> dict[str, str]:
        if not tables:
            return {}
        marks = ",".join("?" * len(tables))
        return {r["name"]: r["fingerprint"] for r in
                self.store.all(f"SELECT name, fingerprint FROM cat_table WHERE name IN ({marks})", tuple(tables))}

    def table_summary(self, table: str) -> dict[str, Any] | None:
        t = self.store.one("SELECT name, rows, comment, description FROM cat_table WHERE name=?", (table,))
        return t

    def describe(self, table: str, learned_joins: list[dict] | None = None) -> dict[str, Any] | None:
        t = self.store.one("SELECT * FROM cat_table WHERE lower(name)=lower(?)", (table,))
        if not t:
            return None
        cols = []
        for c in self.store.all("SELECT * FROM cat_column WHERE table_name=? ORDER BY pos", (t["name"],)):
            entry: dict[str, Any] = {"name": c["name"], "type": c["type"]}
            if c["is_pk"]:
                entry["pk"] = True
            if c["sensitive"]:
                entry["protected"] = True
            stats = json.loads(c["stats"] or "{}")
            for k in ("null_rate", "distinct", "min", "max"):
                if k in stats:
                    entry[k] = stats[k]
            if c["description"] or c["comment"]:
                entry["about"] = c["description"] or c["comment"]
            if c["top_values"]:
                tv = json.loads(c["top_values"])
                entry["values"] = [f"{v['value']} ({v['count']})" for v in tv[:15]]
                if len(tv) > 15:
                    entry["values"].append(f"... {len(tv) - 15} more; use search_values")
            cols.append(entry)
        joins = [dict(r) for r in self.store.all(
            "SELECT * FROM cat_join WHERE from_table=? OR to_table=?", (t["name"], t["name"]))]
        for j in learned_joins or []:
            if t["name"] in (j["from_table"], j["to_table"]):
                joins.append(j)
        return {"table": t["name"], "rows": t["rows"], "about": t["description"] or t["comment"],
                "columns": cols,
                "joins": [f"{j['from_table']}.{j['from_cols']} = {j['to_table']}.{j['to_cols']} ({j['source']})"
                          for j in joins]}

    def join_path(self, start: str, goal: str, learned: list[dict] | None = None) -> list[dict] | None:
        """Cheapest join path. Cost: declared FK 1.0, learned 0.8, inferred 1.5 (lower = preferred)."""
        cost = {"fk": 1.0, "learned": 0.8, "inferred": 1.5}
        edges: dict[str, list[tuple[float, str, dict]]] = {}
        for j in [*self.store.all("SELECT * FROM cat_join"), *(learned or [])]:
            w = cost.get(j["source"], 1.5)
            edges.setdefault(j["from_table"], []).append((w, j["to_table"], j))
            edges.setdefault(j["to_table"], []).append((w, j["from_table"], j))
        heap: list[tuple[float, str, list[dict]]] = [(0.0, start, [])]
        seen: set[str] = set()
        while heap:
            d, node, path = heapq.heappop(heap)
            if node == goal:
                return path
            if node in seen:
                continue
            seen.add(node)
            if len(path) >= 5:
                continue
            for w, nxt, j in edges.get(node, []):
                if nxt not in seen:
                    heapq.heappush(heap, (d + w, nxt, [*path, j]))
        return None
