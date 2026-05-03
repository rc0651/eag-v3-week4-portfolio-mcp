# Zerodha Portfolio MCP

A Python MCP server that connects to Zerodha's Kite Connect API to fetch live portfolio data, display a real-time dashboard, and export holdings to CSV.

## Features

- **Live Holdings & Positions** — fetches CNC and MTF holdings plus open positions from Kite Connect
- **Real-time Dashboard** — standalone HTTP server with live log streaming, gainers/losers breakdown, and P&L coloring
- **CSV Export** — auto-downloads `portfolio.csv` after every analysis run
- **MCP Tools** — usable directly from Claude or any MCP-compatible client
- **Daily Token Renewal** — one-command script to refresh the Kite access token each morning

## Project Structure

```
├── main.py               # FastMCP server with 4 tools
├── serve_dashboard.py    # Standalone HTTP dashboard (port 8888)
├── generate_token.py     # Daily access token renewal script
├── requirements.txt
├── .env                  # API credentials (not committed)
└── .env.example          # Credential template
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in your Kite Connect app credentials:

```
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
KITE_ACCESS_TOKEN=your_access_token_here
```

### 3. Generate a daily access token

Kite access tokens expire at midnight IST. Run this each morning:

```bash
python3 generate_token.py
```

It opens the Kite login page in your browser. After login you are redirected to a URL containing `request_token=XXXX`. Pass that token:

```bash
python3 generate_token.py <request_token>
```

The script saves the new `KITE_ACCESS_TOKEN` directly to `.env`.

## Running the Dashboard

```bash
python3 serve_dashboard.py
```

Opens `http://localhost:8888` automatically. Click **Run Full Analysis** to:

1. Fetch live holdings and open positions from Kite
2. Write `portfolio.csv` (auto-downloaded to your browser)
3. Render the Prefab UI dashboard with gainers, losers, and live log output

## MCP Tools

| Tool | Description |
|------|-------------|
| `fetch_portfolio` | Fetch live holdings from Kite and store in shared state |
| `save_to_file` | Save holdings to `portfolio.csv` |
| `show_dashboard` | Render the Prefab UI dashboard |
| `run_full_analysis` | Chain: fetch → save → dashboard |

### Using with Claude (MCP)

Add to your MCP config:

```json
{
  "mcpServers": {
    "kite-portfolio": {
      "command": "python3",
      "args": ["/path/to/Kite-MCP/main.py"]
    }
  }
}
```

Then ask Claude: *"Run full portfolio analysis"* and it will call the tools in sequence.

## Notes

- MTF (Margin Trading Facility) holdings are handled correctly — quantity and average price are read from the `mtf` sub-object when present
- The dashboard server kills any existing process on port 8888 on startup
- `.env` is git-ignored; never commit real credentials
