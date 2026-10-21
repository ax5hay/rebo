"""One-time capture (run while JMS staging is reachable): human-built JMS reports as a gold set.

Reads custom_report (title, SQL, headers) from staging, pairs each with the natural-language prompt
written for it earlier (prompts.yaml, recovered from git history), screens the SQL for personal
literals, checks each gold SQL runs on the local synthetic copy, and writes
fixtures/jms_staging/gold_custom_reports.jsonl. After this, no JMS access is needed.

    MSYS_NO_PATHCONV=1 aws-vault exec akshay-orchid -- uv run python tools/jms_capture/capture_gold.py \
        --ssm /orchid/app-staging/JMS_DATABASE_URL
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "snapshot"))
from snapshot import _connect, _ssm  # noqa: E402  (same SSM + VPN logic as the structure snapshot)

ROOT = Path(__file__).resolve().parents[2]
_PERSONAL_LITERAL = re.compile(r"('[^']*@[^']*'|'\+?\d[\d\s().-]{6,}')")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssm", required=True)
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--local", default="mysql+pymysql://reports_ro:reports_ro@127.0.0.1:3307/jms")
    ap.add_argument("--out", type=Path, default=ROOT / "fixtures" / "jms_staging" / "gold_custom_reports.jsonl")
    args = ap.parse_args()

    prompts = {r["custom_report_id"]: r for r in yaml.safe_load(
        (Path(__file__).parent / "prompts.yaml").read_text(encoding="utf-8"))["reports"]}
    conn = _connect(_ssm(args.ssm, args.region))
    with conn, conn.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION READ ONLY")
        cur.execute("SELECT custom_report_id, report_title, report_query, report_headers, active, hyperlink "
                    "FROM custom_report WHERE report_query IS NOT NULL AND report_query <> '' ORDER BY custom_report_id")
        reports = list(cur.fetchall())
    local = create_engine(args.local)
    kept, skipped = [], {"personal_literal": 0, "no_prompt": 0}
    for r in reports:
        sql = r["report_query"].strip().rstrip(";")
        if _PERSONAL_LITERAL.search(sql):
            skipped["personal_literal"] += 1
            continue
        p = prompts.get(r["custom_report_id"])
        if not p:
            skipped["no_prompt"] += 1
            continue
        try:
            with local.connect() as c:
                c.execute(text("SET SESSION TRANSACTION READ ONLY"))
                n = len(c.exec_driver_sql(sql).fetchmany(5001))
            runs, err = True, None
        except Exception as e:  # gold SQL that does not run on the local copy is kept but flagged
            runs, err, n = False, str(getattr(e, "orig", e))[:200], None
        kept.append({"id": f"cr-{r['custom_report_id']}", "question": p["prompt"], "gold_sql": sql,
                     "title": r["report_title"], "headers": r["report_headers"], "active": r["active"],
                     "grain": p.get("grain"), "runs_locally": runs, "local_rows": n, "local_error": err,
                     "source": "staging custom_report (human-built) + constructed prompt"})
    args.out.write_text("\n".join(json.dumps(k) for k in kept) + "\n", encoding="utf-8")
    print(json.dumps({"staging_reports": len(reports), "kept": len(kept), "skipped": skipped,
                      "run_locally": sum(k["runs_locally"] for k in kept)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
