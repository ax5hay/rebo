"""Build Orbitra Energy Systems: a made-up company database for testing ReBo at enterprise size.

Orbitra is an Indian maker of smart meters, solar inverters and EV chargers (HQ Pune), with
subsidiaries in the UK, Germany, the US, Singapore and the UAE, and customers worldwide. Everything is
synthetic (Faker, seeded): names, companies, addresses, tax ids and amounts are invented. Nothing here
comes from any real company or from JMS.

    docker compose up -d orbitra-db                                        # PostgreSQL on :5434
    uv run --extra synth python fixtures/orbitra/build.py                  # full size, into Postgres
    uv run --extra synth python fixtures/orbitra/build.py --sqlite /tmp/o.db --scale 0.02   # small copy
    REBO_CONFIG=fixtures/orbitra/rebo.yaml uv run rebo bootstrap
    REBO_CONFIG=fixtures/orbitra/rebo.yaml uv run rebo serve --port 8100

Deliberate, realistic quirks the bot must cope with (learned from people, never configured):
  * transaction currency plus an amount in INR on invoices; fx rates in their own table
  * statuses are free strings in some tables and lookup tables in others
  * a few foreign keys are not declared (manager_id, approver_id, payslip.employee_id, ...)
  * protected columns: password hashes, API tokens, bank account numbers, PAN
  * the Indian fiscal year (April to March) in fiscal_period; GST on Indian invoices, VAT elsewhere
  * header totals are sums of their lines (orders, invoices, purchase orders, expense claims)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import build  # noqa: E402

DEFAULT_URL = "postgresql+psycopg://orbitra:orbitra@127.0.0.1:5434/orbitra"


def all_tables():
    import spec_finance
    import spec_org
    import spec_ops
    import spec_sales
    import spec_service
    import spec_work
    return [*spec_org.TABLES, *spec_sales.TABLES, *spec_finance.TABLES, *spec_ops.TABLES, *spec_service.TABLES,
            *spec_work.TABLES]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("ORBITRA_URL", DEFAULT_URL))
    ap.add_argument("--sqlite", help="build into this SQLite file instead")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    url = f"sqlite:///{a.sqlite}" if a.sqlite else a.url
    t0 = time.time()
    counts = build(all_tables(), url, seed=a.seed, scale=a.scale, echo=lambda s: None)
    total = sum(counts.values())
    print(f"{len(counts)} tables, {total:,} rows in {time.time() - t0:.0f} s -> {url.split('@')[-1]}")
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  {name:28s} {n:>9,}")


if __name__ == "__main__":
    main()
