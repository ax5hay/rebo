"""Snapshot a MySQL database's structure and profile so it can be rebuilt elsewhere.

Writes three files into --out:

  schema.sql    Portable DDL for every table, view, trigger and routine
                (no DEFINER, no AUTO_INCREMENT counters, FK checks off while loading).
  profile.json  Per-table row counts and per-column statistics (type, null rate,
                distinct count, min/max, string lengths) plus categorical value
                catalogs for low-cardinality, non-personal columns. The synthetic
                data generator reads this; it never contains free text or personal data.
  manifest.json Source server version, database name, capture time, object counts.

No row data is copied. Usage (any MySQL source):

    python snapshot.py --url mysql+pymysql://user:pass@host:3306/db --out ../../fixtures/jms_staging

JMS staging (URL from SSM, VPN private-IP rewrite), run under aws-vault:

    aws-vault exec akshay-orchid -- python snapshot.py --ssm /orchid/app-staging/JMS_DATABASE_URL \
        --out ../../fixtures/jms_staging
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import json
import re
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql

# Never catalogued, anywhere: values that identify a person, a tenant or a credential.
_NEVER = re.compile(
    r"(first|last|middle|maiden|email|phone|mobile|fax|ssn|social|address|street|city|zip|"
    r"postal|dob|birth|passport|licen[cs]e|token|password|secret|hash|salt|key|sid$|_sid|"
    r"domain|ip_?addr|signature|account|routing|iban|card|cvv|latitude|longitude|geo|uuid|"
    r"guid|session|cookie|url|link|file|path|from_)",
    re.I,
)
# Free text or person-ish labels: blocked by default ...
_PERSONAL = re.compile(
    r"(name|note|text|answer|desc|comment|body|html|content|message|subject|title|label|"
    r"question|agent|referr?er)",
    re.I,
)
# ... except short label columns of small reference tables that do not describe people
# (status names, stage titles, service levels): the business vocabulary a bot must match.
_LABEL = re.compile(r"(name|title|label|reason|status|stage|type|category|code)$", re.I)
_PERSON_TABLE = re.compile(
    r"(user|admin|contact|agency|clinic|provider|family|profile|person|member|party|lead|"
    r"recipient|staff|employee|customer|patient|donor|parent|baby|child|spouse|partner|"
    r"(^|_)(log|logs|note|notes|message|messages|email|emails|sms|text|history|chat)($|_))", re.I)
_LOOKUP_MAX_ROWS = 2000
_LOOKUP_MAX_DISTINCT = 200
_CATALOG_TYPES = {"enum", "set", "tinyint", "smallint", "char", "varchar", "bit"}
_CATALOG_MAX_DISTINCT = 40
_CATALOG_MAX_VARCHAR = 64
_LOOKS_SENSITIVE = re.compile(r"(@|^gAAAA|^\+?\d[\d\s().-]{6,}$|^\d{3}-\d{2}-\d{4}$)")
_STATS_SKIP_TYPES = {"blob", "longblob", "mediumblob", "tinyblob", "binary", "varbinary",
                     "geometry", "point", "linestring", "polygon"}
_LONG_TEXT = {"text", "mediumtext", "longtext", "tinytext", "json"}


def _ssm(name: str, region: str) -> str:
    return subprocess.check_output(
        ["aws", "ssm", "get-parameter", "--name", name, "--with-decryption",
         "--query", "Parameter.Value", "--output", "text", "--region", region],
        text=True,
    ).strip()


def _tcp_ok(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _rds_private_ip(host: str, port: int) -> str | None:
    """Public RDS endpoint unreachable (VPN-only) -> find a reachable private ENI IP."""
    import boto3

    m = re.search(r"\.([a-z0-9-]+)\.rds\.amazonaws\.com$", host)
    region = m.group(1) if m else "us-east-2"
    rds = boto3.client("rds", region_name=region)
    ec2 = boto3.client("ec2", region_name=region)
    groups: list[str] = []
    for db in rds.describe_db_instances().get("DBInstances", []):
        if db.get("Endpoint", {}).get("Address") == host:
            groups = [g["VpcSecurityGroupId"] for g in db.get("VpcSecurityGroups", [])]
            break
    if not groups:
        return None
    enis = ec2.describe_network_interfaces(Filters=[
        {"Name": "group-id", "Values": groups},
        {"Name": "description", "Values": ["RDSNetworkInterface"]},
    ]).get("NetworkInterfaces", [])
    for eni in enis:
        ip = eni.get("PrivateIpAddress")
        if ip and _tcp_ok(ip, port):
            return ip
    return None


def _connect(url: str):
    u = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    host, port = u.hostname or "localhost", u.port or 3306
    if host.endswith(".rds.amazonaws.com") and not _tcp_ok(host, port, 2.0):
        host = _rds_private_ip(host, port) or host
        print(f"[snapshot] using VPN private IP {host}", file=sys.stderr)
    return pymysql.connect(
        host=host, port=port, user=unquote(u.username or ""), password=unquote(u.password or ""),
        database=u.path.lstrip("/") or None, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor, read_timeout=600,
    )


def _q(cur, sql: str, args=None) -> list[dict]:
    cur.execute(sql, args)
    return list(cur.fetchall())


def _ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _clean_ddl(ddl: str) -> str:
    ddl = re.sub(r"\s+AUTO_INCREMENT=\d+", "", ddl)
    ddl = re.sub(r"DEFINER=`[^`]*`@`[^`]*`\s*", "", ddl)
    ddl = re.sub(r"\s+SQL SECURITY DEFINER", "", ddl)
    return ddl.strip()


def _jsonable(v):
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return str(v)
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray)):
        return int.from_bytes(v, "big") if len(v) <= 8 else None
    return v


def dump_schema(cur, db: str) -> tuple[str, dict]:
    tables = _q(cur, "SELECT table_name AS t, table_type AS k FROM information_schema.tables "
                     "WHERE table_schema=%s ORDER BY table_name", (db,))
    base = [r["t"] for r in tables if r["k"] == "BASE TABLE"]
    views = [r["t"] for r in tables if r["k"] == "VIEW"]
    out = ["-- Structure-only snapshot. Load into an empty database.",
           "SET NAMES utf8mb4;", "SET FOREIGN_KEY_CHECKS=0;", ""]
    for t in base:
        ddl = _q(cur, f"SHOW CREATE TABLE {_ident(t)}")[0]["Create Table"]
        out += [f"DROP TABLE IF EXISTS {_ident(t)};", _clean_ddl(ddl) + ";", ""]
    for v in views:
        try:
            ddl = _q(cur, f"SHOW CREATE VIEW {_ident(v)}")[0]["Create View"]
            out += [f"DROP VIEW IF EXISTS {_ident(v)};", _clean_ddl(ddl) + ";", ""]
        except pymysql.MySQLError as e:
            out.append(f"-- view {v} skipped: {e.args[-1]}")
    trig = _q(cur, "SELECT trigger_name AS n FROM information_schema.triggers "
                   "WHERE trigger_schema=%s", (db,))
    routines = _q(cur, "SELECT routine_name AS n, routine_type AS k FROM information_schema.routines "
                       "WHERE routine_schema=%s", (db,))
    if trig or routines:
        out.append("DELIMITER ;;")
        for r in trig:
            try:
                ddl = _q(cur, f"SHOW CREATE TRIGGER {_ident(r['n'])}")[0]["SQL Original Statement"]
                out += [_clean_ddl(ddl) + ";;", ""]
            except pymysql.MySQLError as e:
                out.append(f"-- trigger {r['n']} skipped: {e.args[-1]}")
        for r in routines:
            kind = r["k"].upper()
            try:
                row = _q(cur, f"SHOW CREATE {kind} {_ident(r['n'])}")[0]
                ddl = row.get(f"Create {kind.title()}")
                if ddl:
                    out += [_clean_ddl(ddl) + ";;", ""]
                else:
                    out.append(f"-- {kind.lower()} {r['n']} body not visible to this user")
            except pymysql.MySQLError as e:
                out.append(f"-- {kind.lower()} {r['n']} skipped: {e.args[-1]}")
        out.append("DELIMITER ;")
    out += ["SET FOREIGN_KEY_CHECKS=1;", ""]
    counts = {"tables": len(base), "views": len(views), "triggers": len(trig), "routines": len(routines)}
    return "\n".join(out), counts


def _catalogable(table: str, rows: int, col: dict, distinct: int | None) -> bool:
    name = col["name"]
    if not distinct or col["data_type"] not in _CATALOG_TYPES:
        return False
    if col["key"] == "PRI" or name.endswith("_id") or name == "id" or _NEVER.search(name):
        return False
    lookup = (rows <= _LOOKUP_MAX_ROWS and _LABEL.search(name) and not _PERSON_TABLE.search(table)
              and col["data_type"] in ("varchar", "char") and (col["char_len"] or 0) <= 255)
    if lookup:
        return distinct <= _LOOKUP_MAX_DISTINCT
    if distinct > _CATALOG_MAX_DISTINCT:
        return False
    if col["data_type"] in ("varchar", "char") and (col["char_len"] or 0) > _CATALOG_MAX_VARCHAR:
        return False
    return not _PERSONAL.search(name)


def profile(cur, db: str) -> dict:
    cols = _q(cur, """
        SELECT table_name AS t, column_name AS name, ordinal_position AS pos,
               data_type AS data_type, column_type AS column_type,
               is_nullable AS nullable, column_key AS `key`, column_default AS dflt, extra AS extra,
               character_maximum_length AS char_len, column_comment AS comment
        FROM information_schema.columns c
        JOIN information_schema.tables USING (table_schema, table_name)
        WHERE table_schema=%s AND table_type='BASE TABLE'
        ORDER BY table_name, ordinal_position""", (db,))
    fks = _q(cur, """
        SELECT table_name AS t, column_name AS c, referenced_table_name AS rt,
               referenced_column_name AS rc, constraint_name AS name
        FROM information_schema.key_column_usage
        WHERE table_schema=%s AND referenced_table_name IS NOT NULL
        ORDER BY table_name, constraint_name, ordinal_position""", (db,))
    comments = {r["t"]: r["c"] for r in _q(cur, "SELECT table_name AS t, table_comment AS c FROM "
                                                "information_schema.tables WHERE table_schema=%s", (db,))}
    by_table: dict[str, list[dict]] = {}
    for c in cols:
        by_table.setdefault(c["t"], []).append(c)

    tables: dict[str, dict] = {}
    for i, (t, tcols) in enumerate(sorted(by_table.items()), 1):
        n = _q(cur, f"SELECT COUNT(*) AS n FROM {_ident(t)}")[0]["n"]
        print(f"[snapshot] {i}/{len(by_table)} {t} rows={n}", file=sys.stderr)
        stats: dict[str, dict] = {}
        measurable = [c for c in tcols if c["data_type"] not in _STATS_SKIP_TYPES]
        if n and measurable:
            parts = []
            for c in measurable:
                q = _ident(c["name"])
                parts.append(f"SUM({q} IS NULL) AS {_ident(c['name'] + '__nulls')}")
                if c["data_type"] in _LONG_TEXT:
                    parts.append(f"AVG(CHAR_LENGTH({q})) AS {_ident(c['name'] + '__avglen')}")
                    parts.append(f"MAX(CHAR_LENGTH({q})) AS {_ident(c['name'] + '__maxlen')}")
                    continue
                parts.append(f"COUNT(DISTINCT {q}) AS {_ident(c['name'] + '__distinct')}")
                if c["data_type"] in ("varchar", "char"):
                    parts.append(f"AVG(CHAR_LENGTH({q})) AS {_ident(c['name'] + '__avglen')}")
                    parts.append(f"MAX(CHAR_LENGTH({q})) AS {_ident(c['name'] + '__maxlen')}")
                elif c["data_type"] not in ("enum", "set"):
                    parts.append(f"MIN({q}) AS {_ident(c['name'] + '__min')}")
                    parts.append(f"MAX({q}) AS {_ident(c['name'] + '__max')}")
            row = _q(cur, f"SELECT {', '.join(parts)} FROM {_ident(t)}")[0]
            for c in measurable:
                s = {k.split("__", 1)[1]: _jsonable(v) for k, v in row.items()
                     if k.split("__", 1)[0] == c["name"] and v is not None}
                if "nulls" in s:
                    s["null_rate"] = round(float(s.pop("nulls")) / n, 4)
                if "avglen" in s:
                    s["avglen"] = round(float(s["avglen"]), 1)
                stats[c["name"]] = s
        columns = []
        for c in tcols:
            s = stats.get(c["name"], {})
            entry = {
                "name": c["name"], "type": c["column_type"], "data_type": c["data_type"],
                "nullable": c["nullable"] == "YES", "key": c["key"] or None,
                "default": c["dflt"], "extra": c["extra"] or None,
                "comment": c["comment"] or None, **s,
            }
            if _catalogable(t, n, c, s.get("distinct")):
                vals = _q(cur, f"SELECT {_ident(c['name'])} AS v, COUNT(*) AS n FROM {_ident(t)} "
                               f"WHERE {_ident(c['name'])} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC")
                clean = [{"value": _jsonable(r["v"]), "count": r["n"]} for r in vals
                         if not _LOOKS_SENSITIVE.search(str(r["v"]))]
                if len(clean) == len(vals):  # any suspicious value -> drop the whole catalog
                    entry["values"] = clean
            columns.append(entry)
        tables[t] = {
            "rows": n, "comment": comments.get(t) or None, "columns": columns,
            "foreign_keys": [{"column": f["c"], "ref_table": f["rt"], "ref_column": f["rc"],
                              "name": f["name"]} for f in fks if f["t"] == t],
        }
    return tables


_REFISH = re.compile(r"(_id|id|_by|_to|_owner)$", re.I)
_INT_TYPES = {"int", "bigint", "smallint", "mediumint"}


def _stem(col: str) -> str:
    return re.sub(r"(_id|id|_by|_to|_owner)$", "", col, flags=re.I).strip("_").lower()


def implicit_refs(cur, tables: dict) -> list[dict]:
    """Undeclared references: integer *_id-like columns (no FK) whose staging values all sit
    inside another table's single-column integer primary key. Measured by value containment;
    only the winning table/column names and the score are written, never the values."""
    pks = {}
    for t, info in tables.items():
        pk = [c for c in info["columns"] if c["key"] == "PRI"]
        if len(pk) == 1 and pk[0]["data_type"] in _INT_TYPES:
            pks[t] = pk[0]["name"]
    fk_cols = {(t, f["column"]) for t, info in tables.items() for f in info["foreign_keys"]}
    cache: dict[str, set] = {}

    def keys(t: str) -> set:
        if t not in cache:
            cache[t] = {r["v"] for r in _q(cur, f"SELECT {_ident(pks[t])} AS v FROM {_ident(t)}")}
        return cache[t]

    out = []
    for t, info in sorted(tables.items()):
        for c in info["columns"]:
            name = c["name"]
            if (c["data_type"] not in _INT_TYPES or c["key"] == "PRI" or (t, name) in fk_cols
                    or not _REFISH.search(name) or (c.get("distinct") or 0) < 3):
                continue
            vals = {r["v"] for r in _q(cur, f"SELECT DISTINCT {_ident(name)} AS v FROM {_ident(t)} "
                                            f"WHERE {_ident(name)} IS NOT NULL AND {_ident(name)} <> 0 LIMIT 5000")}
            if len(vals) < 3:
                continue
            stem = _stem(name)
            cands = []
            for pt, pc in pks.items():
                pv = keys(pt)
                if len(pv) < len(vals):
                    continue
                share = len(vals & pv) / len(vals)
                if share < 0.95:
                    continue
                sim = 2.0 if pc.lower() == name.lower() and pt != t else (
                    1.5 if stem and (stem == pt.lower() or stem in pt.lower() or pt.lower() in stem) else 0.0)
                cands.append((sim, share, -len(pv), pt, pc))
            if not cands:
                continue
            cands.sort(reverse=True)
            best = cands[0]
            out.append({"table": t, "column": name, "ref_table": best[3], "ref_column": best[4],
                        "containment": round(best[1], 3), "by_name": best[0] > 0,
                        "alternatives": [f"{x[3]}.{x[4]}" for x in cands[1:4]] if best[0] == 0 else []})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="mysql+pymysql://user:pass@host:port/db")
    src.add_argument("--ssm", help="SSM parameter name holding the URL (needs AWS creds)")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--no-values", action="store_true", help="skip categorical value catalogs")
    args = ap.parse_args()

    url = args.url or _ssm(args.ssm, args.region)
    args.out.mkdir(parents=True, exist_ok=True)
    conn = _connect(url)
    with conn, conn.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION READ ONLY")
        meta = _q(cur, "SELECT DATABASE() AS db, VERSION() AS v, @@character_set_database AS cs, "
                       "@@collation_database AS co, @@sql_mode AS mode")[0]
        db = meta["db"]
        ddl, counts = dump_schema(cur, db)
        (args.out / "schema.sql").write_text(ddl, encoding="utf-8")
        tables = profile(cur, db)
        if args.no_values:
            for t in tables.values():
                for c in t["columns"]:
                    c.pop("values", None)
        refs = implicit_refs(cur, tables)
        print(f"[snapshot] {len(refs)} implicit references measured", file=sys.stderr)
        (args.out / "profile.json").write_text(
            json.dumps({"tables": tables, "implicit_refs": refs}, indent=1, default=str), encoding="utf-8")
        manifest = {
            "source_database": db, "server_version": meta["v"], "charset": meta["cs"],
            "collation": meta["co"], "sql_mode": meta["mode"],
            "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "objects": counts,
            "rows_total": sum(t["rows"] for t in tables.values()),
            "columns_total": sum(len(t["columns"]) for t in tables.values()),
            "foreign_keys_total": sum(len(t["foreign_keys"]) for t in tables.values()),
            "catalogued_columns": sum(1 for t in tables.values() for c in t["columns"] if "values" in c),
            "implicit_refs": len(refs),
            "row_data_copied": False,
        }
        (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
