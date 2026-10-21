"""Run scripted multi-turn conversations and save a results file: turns to the first correct report,
clarify rate and cost. Model choice comes from reportsbot.yaml / REPORTSBOT_* env.

    uv run python tools/eval_conversations.py fixtures/demo_property/conversations.jsonl \
        fixtures/demo_property/eval_conversations_<name>.json [limit]

Format: reportsbot.evals.run_conversations.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from reportsbot.evals import run_conversations
from reportsbot.service import App


async def main(cases: str, out: str, limit: int = 0) -> None:
    app = App()
    res = await run_conversations(app, cases, limit=limit)
    doc = {"run": time.strftime("%Y-%m-%d"), "model": app.settings.model, "fast_model": app.settings.fast_model,
           "escalate": app.settings.escalate_model,
           "database": app.target.engine.url.render_as_string(hide_password=True), **res}
    Path(out).write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    print(json.dumps(res["summary"]))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0))
