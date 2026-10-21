"""Command line: `reportsbot <command>`. See docs/12-operations.md."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reportsbot", description="Self-learning reports bot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bootstrap", help="read, profile and index the target database")
    b.add_argument("--describe", action="store_true", help="also draft table/column descriptions with the fast LLM")
    s = sub.add_parser("serve", help="HTTP API + chat UI")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    s.add_argument("--no-ui", action="store_true")
    a = sub.add_parser("ask", help="one question from the terminal")
    a.add_argument("text")
    a.add_argument("--user", default="cli")
    a.add_argument("--role", default="user", choices=["user", "admin", "owner"])
    sub.add_parser("revalidate", help="re-check saved knowledge after schema changes")
    e = sub.add_parser("eval", help="run an eval set (JSONL of {id, question, ...})")
    e.add_argument("path")
    e.add_argument("--limit", type=int, default=0)
    sub.add_parser("mcp", help="serve the read-only tools over MCP (stdio)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from .service import App

    if args.cmd == "mcp":
        from .mcp_server import serve_mcp
        serve_mcp(App())
        return 0
    app = App()
    if args.cmd == "bootstrap":
        app.bootstrap(describe=args.describe)
    elif args.cmd == "serve":
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(app, with_ui=not args.no_ui), host=args.host, port=args.port)
    elif args.cmd == "ask":
        from .knowledge import User
        r = asyncio.run(app.ask(User(args.user, args.role), args.text))
        if r.get("kind") == "report":
            r["rows"] = r["rows"][:20]  # the terminal shows a preview; the API returns everything
        print(json.dumps(r, indent=2, default=str))
    elif args.cmd == "revalidate":
        print(json.dumps(app.revalidate(), indent=2))
    elif args.cmd == "eval":
        from .evals import run_eval
        print(json.dumps(asyncio.run(run_eval(app, args.path, limit=args.limit)), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
