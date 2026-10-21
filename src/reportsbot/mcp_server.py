"""Optional MCP adapter: exposes the same read-only tools to any MCP client (Claude Code,
Claude Desktop, IDEs). Same guard, same limits, same catalog. Learning stays in the bot's
own UI/API because confirmations need an identified person. See docs/09-api-and-ui.md.
"""
from __future__ import annotations

from typing import Any

from .safety import guard
from .service import App


def serve_mcp(app: App) -> None:
    from fastmcp import FastMCP

    mcp = FastMCP("reportsbot")

    @mcp.tool
    def search_schema(query: str) -> list[dict[str, Any]]:
        """Find tables and columns related to some business words."""
        return app.index.search_schema(query)

    @mcp.tool
    def describe_table(table: str) -> dict[str, Any] | None:
        """Columns, statistics, common values and joins of one table."""
        return app.catalog.describe(table)

    @mcp.tool
    def search_values(text: str) -> list[dict[str, Any]]:
        """Where a literal value is stored (table, column, exact value, frequency)."""
        return app.index.search_values(text)

    @mcp.tool
    def run_sql(sql: str) -> dict[str, Any]:
        """Run one read-only SELECT (guarded, row-capped, timed out)."""
        g = guard(sql, dialect=app.target.dialect, schema=app.catalog.schema, sensitive=app.catalog.sensitive,
                  allowed_tables=app.allowed_tables, row_cap=app.settings.row_limit + 1)
        r = app.target.run(g.sql, max_rows=app.settings.row_limit)
        return {"columns": r.columns, "rows": r.rows, "truncated": r.truncated}

    @mcp.tool
    def verified_reports(query: str) -> list[dict[str, Any]]:
        """Reports an admin verified for everyone, best match first."""
        from .knowledge import User
        anyone = User(id="__mcp__")
        return [app.knowledge_for_prompt(i, anyone) for i in app.knowledge.search(anyone, query)
                if i["status"] == "verified"]

    mcp.run()
