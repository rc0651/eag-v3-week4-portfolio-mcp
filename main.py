import os
import csv
from dotenv import load_dotenv
from fastmcp import FastMCP
from kiteconnect import KiteConnect
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Column, Row, Heading, Separator, Text,
    Card, ForEach, Rx, Button,
)
from prefab_ui.actions.mcp import CallTool

load_dotenv()

mcp = FastMCP(
    "Kite Portfolio MCP",
    instructions=(
        "When user asks for portfolio analysis, run fetch_portfolio → "
        "save_to_file → show_dashboard in sequence."
    ),
)

kite = KiteConnect(api_key=os.getenv("KITE_API_KEY"))
kite.set_access_token(os.getenv("KITE_ACCESS_TOKEN"))

# Shared in-process state between tools
portfolio_state: dict = {"holdings": [], "total_pnl": 0.0, "total_pnl_str": "0.00"}


def _fmt_pnl(pnl: float) -> str:
    return f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"


# ── Tool 1 ──────────────────────────────────────────────────────────────────

@mcp.tool()
def fetch_portfolio() -> str:
    """Fetch live holdings from Kite and store in shared state."""
    global portfolio_state

    raw = kite.holdings()
    holdings = []
    for h in raw:
        mtf      = h.get("mtf") or {}
        quantity = mtf.get("quantity") or h["quantity"]
        avg      = mtf.get("average_price") or h["average_price"]
        pnl      = round((h["last_price"] - avg) * quantity, 2)
        holdings.append({
            "symbol":     h["tradingsymbol"],
            "quantity":   quantity,
            "avg_price":  round(avg, 2),
            "last_price": round(h["last_price"], 2),
            "pnl":        pnl,
            "pnl_str":    _fmt_pnl(pnl),
        })

    total_pnl = round(sum(h["pnl"] for h in holdings), 2)
    portfolio_state = {
        "holdings":      holdings,
        "total_pnl":     total_pnl,
        "total_pnl_str": _fmt_pnl(total_pnl),
    }
    return f"Fetched {len(holdings)} holdings. Total P&L: {portfolio_state['total_pnl_str']}"


# ── Tool 2 ──────────────────────────────────────────────────────────────────

@mcp.tool()
def save_to_file() -> str:
    """Save portfolio holdings from shared state to portfolio.csv."""
    holdings = portfolio_state.get("holdings", [])
    if not holdings:
        return "No holdings found. Run fetch_portfolio first."

    filepath = "portfolio.csv"
    fields = ["symbol", "quantity", "avg_price", "last_price", "pnl"]
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(holdings)

    return f"Saved {len(holdings)} holdings to {filepath}"


# ── Tool 3 ──────────────────────────────────────────────────────────────────

@mcp.tool(app=True)
def show_dashboard() -> PrefabApp:
    """Show a portfolio dashboard: gainers first, then losers, with per-card P&L coloring."""
    if not portfolio_state.get("holdings"):
        fetch_portfolio()

    holdings      = portfolio_state.get("holdings", [])
    total_pnl_str = portfolio_state.get("total_pnl_str", "0.00")

    def _enrich(h: dict) -> dict:
        pnl = h["pnl"]
        pnl_class = (
            "text-green-600 font-medium" if pnl > 0 else
            "text-red-600 font-medium"   if pnl < 0 else
            "text-gray-500 font-medium"
        )
        return {**h, "pnl_class": pnl_class}

    gainers = sorted(
        [_enrich(h) for h in holdings if h["pnl"] > 0],
        key=lambda h: h["pnl"], reverse=True,
    )
    losers = sorted(
        [_enrich(h) for h in holdings if h["pnl"] <= 0],
        key=lambda h: h["pnl"],
    )

    state = {
        "gainers":       gainers,
        "losers":        losers,
        "total_pnl_str": total_pnl_str,
    }

    with PrefabApp(title="My Zerodha Portfolio", state=state, css_class="p-6 space-y-4") as app:
        with Row(css_class="items-center justify-between"):
            Heading("My Zerodha Portfolio")
            Button("Fetch Portfolio", on_click=CallTool("fetch_portfolio"))
        Heading(f"Total P&L: ₹{Rx('total_pnl_str')}")
        Separator()

        # ── Gainers ──────────────────────────────────────────────────────────
        with ForEach("gainers") as item:
            with Card(css_class="p-4 mb-2"):
                with Column(css_class="gap-1"):
                    Text(f"{item.symbol}", bold=True)
                    Text(f"{item.pnl_str}", css_class=f"{item.pnl_class}")
                    Text(f"₹{item.last_price}  ·  Avg ₹{item.avg_price}")

        Separator()

        # ── Losers ───────────────────────────────────────────────────────────
        with ForEach("losers") as item:
            with Card(css_class="p-4 mb-2"):
                with Column(css_class="gap-1"):
                    Text(f"{item.symbol}", bold=True)
                    Text(f"{item.pnl_str}", css_class=f"{item.pnl_class}")
                    Text(f"₹{item.last_price}  ·  Avg ₹{item.avg_price}")

    return app


@mcp.tool()
def run_full_analysis() -> str:
    """Run the complete portfolio pipeline: fetch → save to CSV → show dashboard."""
    step1 = fetch_portfolio()
    step2 = save_to_file()
    return f"Analysis complete.\n1. {step1}\n2. {step2}\n3. Call show_dashboard to view the Prefab UI."


if __name__ == "__main__":
    mcp.run()
