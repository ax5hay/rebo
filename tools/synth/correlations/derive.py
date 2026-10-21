"""Derive the date-order spec for tools/synth from a profile (B-042).

    uv run python tools/synth/correlations/derive.py fixtures/jms_staging/profile.json \
        > tools/synth/correlations/jms_staging.json

Within one row, dates follow tiers taken from their column names: born < created < started <
ended < touched (e.g. date_of_birth < created < start_date < completed < last_updated). Columns
whose names say nothing about order (deadlines such as *_due_date / must_be_*_by, bare "date") get
no tier and stay independent. The output is meant to be read and edited by hand: delete a column
from a table's list to free it, or move it to another tier.

Why not NeMo Data Designer (data-designer 0.9.6, Apache-2.0, checked 2026-10-21): pre-1.0, pulls in
pandas, pyarrow, the Hugging Face hub and Prometheus, and is built around LLM-generated columns;
our profile has per-column statistics only (no joint distributions: JMS is unreachable), so the
dependencies it can express beyond these orderings could not be grounded in the source anyway.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TIERS = [  # (tier, regex on the column name), first match wins
    (0, r"(^|_)(date_of_birth|dob)$"),
    (None, r"(due|deadline|must_be_.*_by|projected|expected|scheduled)"),
    (1, r"^(created|created_at|date_created|added|registered)$"),
    (2, r"^(start_date|started_at|first_occurred|referral_date|sign_on_date|opened|sent_at|requested_at)$"),
    (3, r"^(completed|completed_at|closed|closed_at|end_date|date_end|resolved_at|deleted_at|removed|"
        r"last_occurred|finished_at|signed_at|uploaded)$|_disabled_at$"),
    (4, r"^(updated|updated_at|last_updated|last_updated_dt|modified|last_login|last_sync_at|last_full_sync_at|"
        r"synced_at|last_message_at|last_signaled_at|last_attempt_at)$"),
]
DATE_TYPES = {"date", "datetime", "timestamp"}


def tier(name: str) -> int | None:
    for t, rx in TIERS:
        if re.search(rx, name):
            return t
    return None


def derive(profile: dict) -> dict:
    out = {}
    for table, info in sorted(profile["tables"].items()):
        cols = [(c["name"], tier(c["name"])) for c in info["columns"] if c.get("data_type") in DATE_TYPES]
        ranked = sorted([(n, t) for n, t in cols if t is not None], key=lambda x: (x[1], x[0]))
        if len({t for _, t in ranked}) > 1:  # an order needs at least two tiers
            out[table] = [[n, t] for n, t in ranked]
    return {"rule": "within a row, a date of a higher tier is never earlier than one of a lower tier",
            "tiers": {"0": "born", "1": "created", "2": "started", "3": "ended", "4": "touched"},
            "tables": out}


if __name__ == "__main__":
    print(json.dumps(derive(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))), indent=1))
