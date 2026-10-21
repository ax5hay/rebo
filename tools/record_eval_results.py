"""Record existing eval results files in a state store, so Insights shows their history.

    REBO_CONFIG=fixtures/demo_property/rebo.yaml uv run python tools/record_eval_results.py \
        fixtures/demo_property/eval_results_*.json fixtures/demo_property/eval_conversations_*.json

The run date comes from the file ("run": YYYY-MM-DD); files already recorded are skipped.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from rebo.evals import record_run
from rebo.service import App


def main(paths: list[str]) -> None:
    app = App()
    known = {r["results_file"] for r in app.store.all("SELECT results_file FROM eval_run")}
    for p in paths:
        if p in known:
            continue
        doc = json.loads(Path(p).read_text(encoding="utf-8"))
        at = dt.datetime.fromisoformat(doc["run"]).timestamp() if doc.get("run") else None
        kind = "conversations" if "conversations" in doc else "questions"
        record_run(app, kind=kind, cases=doc.get("cases_file") or Path(p).parent.name, model=doc.get("model"),
                   summary=doc["summary"], results_file=p, at=at)
        print("recorded", p)


if __name__ == "__main__":
    main(sys.argv[1:])
