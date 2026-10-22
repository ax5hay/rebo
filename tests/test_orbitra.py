"""The Orbitra company database (fixtures/orbitra): a small build must be a coherent company, and every
gold question must refer to tables and columns that exist. No model, no Docker."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
import sqlglot
from sqlglot import exp

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("faker")


@pytest.fixture(scope="module")
def orbitra(tmp_path_factory):
    sys.path.insert(0, str(ROOT / "fixtures" / "orbitra"))
    import build
    from engine import build as run
    db = tmp_path_factory.mktemp("orbitra") / "orbitra.db"
    counts = run(build.all_tables(), f"sqlite:///{db}", seed=7, scale=0.03, echo=lambda s: None)
    return db, counts


def test_it_is_a_large_company_database(orbitra):
    _, counts = orbitra
    assert len(counts) >= 200 and sum(counts.values()) > 50_000


def test_books_and_documents_agree(orbitra):
    con = sqlite3.connect(orbitra[0])
    one = lambda sql: (con.execute(sql).fetchone() or [None])[0]  # noqa: E731
    assert one("SELECT COUNT(*) FROM (SELECT journal_entry_id FROM journal_line GROUP BY 1 HAVING ABS(SUM(debit) - SUM(credit)) > 0.01)") == 0
    assert one("SELECT COUNT(*) FROM ar_invoice i JOIN sales_order o USING (sales_order_id) WHERE ABS(i.total_amount - o.total_amount) > 0.01") == 0
    assert one("SELECT COUNT(*) FROM ar_receipt r JOIN ar_invoice i USING (ar_invoice_id) WHERE r.receipt_date < i.invoice_date") == 0
    assert one("SELECT COUNT(*) FROM ar_invoice i WHERE (SELECT SUM(amount) FROM ar_receipt r WHERE r.ar_invoice_id = i.ar_invoice_id) > i.total_amount + 0.01") == 0
    assert one("SELECT COUNT(*) FROM payslip GROUP BY payroll_run_id, employee_id HAVING COUNT(*) > 1") is None   # one payslip per person per run
    assert one("SELECT COUNT(*) FROM expense_claim c WHERE ABS(total_amount - (SELECT SUM(amount) FROM expense_line l WHERE l.expense_claim_id = c.expense_claim_id)) > 0.01") == 0
    statuses = {r[0] for r in con.execute("SELECT DISTINCT status FROM ar_invoice")}
    assert {"Paid", "Partially paid", "Overdue"} <= statuses


def test_every_gold_question_uses_tables_and_columns_that_exist(orbitra):
    con = sqlite3.connect(orbitra[0])
    schema = {t: {c[1] for c in con.execute(f"PRAGMA table_info({t})")}
              for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    cases = [json.loads(line) for line in (ROOT / "fixtures" / "orbitra" / "gold.jsonl").read_text(encoding="utf-8").splitlines() if line]
    assert len(cases) >= 40
    for c in cases:
        tree = sqlglot.parse_one(c["gold_sql"], read="postgres")
        aliases = {t.alias_or_name: t.name for t in tree.find_all(exp.Table)}
        for t in aliases.values():
            assert t in schema, f"{c['id']}: no table {t}"
        for col in tree.find_all(exp.Column):
            if col.table in aliases:
                assert col.name in schema[aliases[col.table]], f"{c['id']}: no column {col.table}.{col.name}"
