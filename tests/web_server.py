"""A bot server for the web front end's Playwright tests: the offline 'shop' database and a scripted
FunctionModel instead of an LLM. Not a test module itself.

    uv run python tests/web_server.py --port 8765
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

import uvicorn
from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

sys.path.insert(0, str(Path(__file__).parent))
from conftest import SHOP  # noqa: E402

from rebo.agent import build_agent  # noqa: E402
from rebo.api import create_app  # noqa: E402
from rebo.service import App  # noqa: E402
from rebo.settings import Settings  # noqa: E402


def report(status: str, **extra) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart("present_report", {
        "title": f"{status.title()} customers", "assumptions": [f"{status.title()} means the stored status `{status}`."],
        "sql": f"SELECT full_name AS customer, status FROM customer WHERE status = '{status}'", **extra})])


def model(messages, info) -> ModelResponse:
    prompt = [p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart)][-1]
    request = (re.search(r"<request>(.*)</request>", prompt, re.S) or re.search("(.*)", prompt)).group(1).strip().lower()
    if "per month" in request:
        return ModelResponse(parts=[ToolCallPart("present_report", {
            "title": "Order value per month", "assumptions": ["Month of `placed_at`."],
            "sql": "SELECT substr(placed_at, 1, 7) AS month, SUM(amount) AS order_value, COUNT(*) AS orders "
                   "FROM orders GROUP BY month ORDER BY month"})])
    if request.startswith("correction to the previous report"):
        return report("active")
    if request in ("paused", "closed"):
        return report(request)
    if "paused" in request:
        return report("paused", follow_ups=["Closed customers too"], learnable=[
            {"kind": "term", "title": "on hold", "body": "a customer whose status is paused"}])
    if "closed" in request:
        return report("closed")
    return ModelResponse(parts=[ToolCallPart("ask_clarifying_question", {
        "why": "Customers are stored with several statuses.",
        "questions": [{"question": "Which customers?", "options": ["paused", "closed"]}]})])


def build(tmp: Path) -> App:
    db = tmp / "shop.db"
    con = sqlite3.connect(db)
    con.executescript(SHOP)
    statuses = ["active", "active", "paused", "closed"]
    for i in range(1, 41):
        con.execute("INSERT INTO customer VALUES (?,?,?,?,?,?)", (i, f"Person {i}", f"p{i}@example.com",
                                                                 statuses[i % 4], "x", "2026-01-01"))
    for i in range(1, 121):  # nine months of orders, for the chart test
        con.execute("INSERT INTO orders VALUES (?,?,?,?,?)",
                    (i, 1 + i % 40, 10.0 * i, "shipped", f"2026-0{1 + i % 9}-15"))
    con.commit()
    con.close()
    app = App(Settings(database_url=f"sqlite:///{db}", state_dir=tmp / "state", embeddings=False))
    app.bootstrap(progress=lambda *_: None)
    app.__dict__["agent"] = build_agent(FunctionModel(model))
    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--ui", action="store_true", help="also mount the NiceGUI pages (screenshots, B-043)")
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp())
    # the owner's configuration page shows (and saves to) a throw-away copy of the example, never rebo.yaml
    (tmp / "rebo.yaml").write_text((Path(__file__).parents[1] / "rebo.example.yaml").read_text())
    os.environ["REBO_CONFIG"] = str(tmp / "rebo.yaml")
    uvicorn.run(create_app(build(Path(tempfile.mkdtemp())), with_ui=args.ui), host="127.0.0.1", port=args.port)
