"""
talk2MCP.py — MCP client demo for the Zerodha Portfolio MCP server.

What is MCP?
------------
Model Context Protocol (MCP) is an open standard that lets AI models (like Claude)
talk to external tools and data sources in a structured, consistent way. Instead of
hardcoding API calls inside a prompt, you expose capabilities as "tools" via an MCP
server. The AI discovers the tools at runtime and calls them by name with typed args.

What we built in this project (main.py):
-----------------------------------------
  FastMCP server — "Kite Portfolio MCP" — with 4 tools:

  1. fetch_portfolio     → calls kite.holdings() + kite.positions(), stores in state
  2. save_to_file        → writes portfolio.csv from in-memory state
  3. show_dashboard      → renders a Prefab UI dashboard (gainers/losers/P&L)
  4. run_full_analysis   → chains fetch_portfolio → save_to_file in one shot

  Key design choices:
  - @mcp.tool()          registers a plain function as an MCP tool
  - @mcp.tool(app=True)  registers a tool that returns a PrefabApp (UI response)
  - Shared in-process state (portfolio_state dict) lets tools pass data between calls
  - MTF-aware P&L: MTF holdings show quantity=0 in the root object; real data lives
    in h["mtf"]["quantity"] and h["mtf"]["average_price"]

  Claude workflow instructed via server instructions:
    "When user asks for portfolio analysis, run fetch_portfolio →
     save_to_file → show_dashboard in sequence."

What we built in serve_dashboard.py:
--------------------------------------
  A standalone ThreadedHTTPServer on port 8888 that:
  - Renders the same Prefab UI as main.py (without needing Claude)
  - Streams live logs to the browser via /logs polling every 250ms
  - Triggers CSV auto-download when analysis completes
  - Exposes endpoints: / (dashboard), /run, /reset, /logs, /download

This file (talk2MCP.py):
--------------------------
  Uses FastMCP's async Client to connect directly to the MCP server in-process
  and call each tool — the same way Claude would call them over the protocol.
"""

import asyncio
import os
from dotenv import load_dotenv
from fastmcp import Client

load_dotenv(override=True)


async def main():
    # Connect to the MCP server in-process (imports main.py's `mcp` object)
    # FastMCP Client supports in-process, stdio, and HTTP transports transparently.
    from main import mcp

    async with Client(mcp) as client:

        # ── 1. Discover available tools ───────────────────────────────────────
        print("=" * 60)
        print("  Zerodha Portfolio MCP — available tools")
        print("=" * 60)
        tools = await client.list_tools()
        for tool in tools:
            print(f"  • {tool.name:20s} — {tool.description}")
        print()

        # ── 2. Call fetch_portfolio ───────────────────────────────────────────
        print("─" * 60)
        print("  Calling: fetch_portfolio()")
        print("─" * 60)
        result = await client.call_tool("fetch_portfolio", {})
        for r in result:
            print(" ", r.text)
        print()

        # ── 3. Call save_to_file ──────────────────────────────────────────────
        print("─" * 60)
        print("  Calling: save_to_file()")
        print("─" * 60)
        result = await client.call_tool("save_to_file", {})
        for r in result:
            print(" ", r.text)
        print()

        # ── 4. Call run_full_analysis (chains both above) ─────────────────────
        print("─" * 60)
        print("  Calling: run_full_analysis()")
        print("─" * 60)
        result = await client.call_tool("run_full_analysis", {})
        for r in result:
            print(" ", r.text)
        print()

        print("=" * 60)
        print("  Done. Call show_dashboard() from Claude for the Prefab UI.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
