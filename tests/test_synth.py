"""Synthetic data generator (tools/synth): date order within a row (B-042)."""
import datetime as dt
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


synth = _load("synth", ROOT / "tools" / "synth" / "synth.py")
derive = _load("derive", ROOT / "tools" / "synth" / "correlations" / "derive.py")


def test_tiers_from_column_names():
    assert [derive.tier(n) for n in ("date_of_birth", "created", "start_date", "completed", "last_updated")] == \
        [0, 1, 2, 3, 4]
    assert derive.tier("must_be_completed_by") is None and derive.tier("original_due_date") is None
    assert derive.tier("gc_disabled_at") == 3 and derive.tier("date") is None


def test_generated_dates_keep_their_order():
    col = lambda c, dtype, nul="YES": {"c": c, "dt": dtype, "ct": dtype, "nul": nul, "ex": "", "len": None, "ns": None}
    tables = {"case": {"columns": [col("id", "int", "NO"), col("created", "datetime"), col("completed", "date"),
                                   col("last_updated", "datetime")], "pk": ["id"], "fks": [], "uniques": []}}
    stats = lambda n: {"name": n, "null_rate": 0, "min": "2022-01-01", "max": "2026-10-01"}
    profile = {"tables": {"case": {"rows": 400, "columns": [stats("created"), stats("completed"),
                                                            stats("last_updated")]}}}
    spec = derive.derive({"tables": {"case": {"columns": [{"name": n, "data_type": "datetime"} for n in
                                                          ("created", "completed", "last_updated")]}}})
    as_dt = lambda v: v if isinstance(v, dt.datetime) else dt.datetime.combine(v, dt.time())
    plain = synth.Generator(tables, profile, cap=400, scale=1, min_rows=0, seed=1).table("case")
    assert any(as_dt(r["completed"]) < r["created"] for r in plain)                 # independent before
    rows = synth.Generator(tables, profile, cap=400, scale=1, min_rows=0, seed=1, correlations=spec).table("case")
    assert len(rows) == 400 and all(as_dt(r["created"]) <= as_dt(r["completed"]) <= r["last_updated"] for r in rows)
    gen = synth.Generator(tables, profile, cap=1, scale=1, min_rows=0, seed=1, correlations=spec)
    for hour in range(24):                       # a DATE bumped after a late DATETIME moves to a later day
        row = {"created": dt.datetime(2026, 5, 3, hour, 30), "completed": dt.date(2026, 5, 1), "last_updated": None}
        gen._order_dates("case", row)
        assert dt.datetime.combine(row["completed"], dt.time()) >= row["created"]
    assert all(isinstance(r["completed"], dt.date) and not isinstance(r["completed"], dt.datetime) for r in rows)


def test_the_committed_jms_spec_names_real_date_columns():
    profile = json.loads((ROOT / "fixtures" / "jms_staging" / "profile.json").read_text(encoding="utf-8"))["tables"]
    spec = json.loads((ROOT / "tools" / "synth" / "correlations" / "jms_staging.json").read_text(encoding="utf-8"))
    for table, cols in spec["tables"].items():   # hand edits are allowed; references must stay real
        types = {c["name"]: c.get("data_type") for c in profile[table]["columns"]}
        assert all(types.get(c) in derive.DATE_TYPES for c, _ in cols), table
