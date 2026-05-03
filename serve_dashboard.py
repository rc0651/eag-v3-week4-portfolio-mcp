import os, csv, webbrowser, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from socketserver import ThreadingMixIn
import json
from dotenv import load_dotenv
from kiteconnect import KiteConnect
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Column, Row, Heading, Separator, Text, Card, ForEach, Button,
)

load_dotenv(override=True)

kite = KiteConnect(api_key=os.getenv("KITE_API_KEY"))
kite.set_access_token(os.getenv("KITE_ACCESS_TOKEN"))

CSV_PATH = os.path.join(os.path.dirname(__file__), "portfolio.csv")

# ── Shared state ──────────────────────────────────────────────────────────────
_lock          = threading.Lock()
_status        = "idle"          # idle | running | done | error
_logs:    list = ["🟡 Ready — click Run Full Analysis to start."]
_holdings:list = []
_positions:list= []
_csv_rows:list = []
_total_pnl_str = "—"


def _fmt(pnl):
    return f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"

def _cls(pnl):
    return ("text-green-500 font-semibold" if pnl > 0 else
            "text-red-500 font-semibold"   if pnl < 0 else
            "text-gray-400 font-semibold")

def _log(msg):
    with _lock:
        _logs.append(msg)


def reset():
    global _status, _logs, _holdings, _positions, _csv_rows, _total_pnl_str
    with _lock:
        _status        = "idle"
        _logs          = ["🔄 Reset — click Run Full Analysis to start fresh."]
        _holdings      = []
        _positions     = []
        _csv_rows      = []
        _total_pnl_str = "—"


def run_full_analysis():
    global _status, _holdings, _positions, _csv_rows, _total_pnl_str
    with _lock:
        _status = "running"
        _logs.clear()

    try:
        # ── MCP Handshake ─────────────────────────────────────────────────────
        _log("🔌 MCP Server: Zerodha Portfolio MCP — initialized")
        _log("📡 Tool called: run_full_analysis()")
        _log("─" * 48)

        # ── Step 1a: Holdings ─────────────────────────────────────────────────
        _log("▶  STEP 1 / 3 — Fetching data from Zerodha")
        _log("   🌐 Calling Kite API → kite.holdings() ...")
        raw = kite.holdings()
        holdings = []
        for h in raw:
            mtf = h.get("mtf") or {}
            qty = mtf.get("quantity") or h["quantity"]
            avg = mtf.get("average_price") or h["average_price"]
            pnl = round((h["last_price"] - avg) * qty, 2)
            src = "MTF" if mtf.get("quantity") else "CNC"
            holdings.append({
                "symbol":    h["tradingsymbol"], "type": src,
                "quantity":  qty, "avg_price":  round(avg, 2),
                "last_price":round(h["last_price"], 2),
                "pnl": pnl,  "pnl_str": _fmt(pnl), "pnl_class": _cls(pnl),
            })
            _log(f"   ✅ Holding → {h['tradingsymbol']} | {src} | qty={qty} | "
                 f"avg=₹{avg:.2f} | ltp=₹{h['last_price']:.2f} | P&L={_fmt(pnl)}")

        # ── Step 1b: Positions ────────────────────────────────────────────────
        _log("   🌐 Calling Kite API → kite.positions() ...")
        net = kite.positions().get("net", [])
        positions = []
        for p in net:
            if p["quantity"] == 0:
                continue
            pnl = round(p["pnl"], 2)
            positions.append({
                "symbol":    p["tradingsymbol"], "product": p["product"],
                "quantity":  p["quantity"],      "avg_price": round(p["average_price"], 2),
                "last_price":round(p["last_price"], 2),
                "pnl": pnl,  "pnl_str": _fmt(pnl), "pnl_class": _cls(pnl),
            })
            _log(f"   ✅ Position → {p['tradingsymbol']} | {p['product']} | "
                 f"qty={p['quantity']} | P&L={_fmt(pnl)}")

        _log(f"   📊 Fetched {len(holdings)} holdings + {len(positions)} open positions")
        _log("─" * 48)

        # ── Step 2: Save CSV ──────────────────────────────────────────────────
        _log("▶  STEP 2 / 3 — CRUD: writing portfolio.csv")
        _log(f"   💾 Creating file → {CSV_PATH}")
        fields = ["symbol","type","quantity","avg_price","last_price","pnl"]
        with open(CSV_PATH, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(holdings)
        with open(CSV_PATH, newline="") as f:
            rows = list(csv.DictReader(f))
        _log(f"   ✅ portfolio.csv written — {len(rows)} rows, "
             f"{os.path.getsize(CSV_PATH)} bytes")
        _log("   📥 CSV download will trigger automatically ...")
        _log("─" * 48)

        # ── Step 3: Dashboard ─────────────────────────────────────────────────
        _log("▶  STEP 3 / 3 — Building Prefab UI Dashboard")
        _log("   🎨 Rendering Prefab components: Heading, Card, ForEach, Text ...")
        total_pnl = round(sum(h["pnl"] for h in holdings + positions), 2)
        with _lock:
            _holdings      = holdings
            _positions     = positions
            _csv_rows      = rows
            _total_pnl_str = _fmt(total_pnl)
        _log(f"   ✅ Dashboard state built — Total P&L: ₹{_fmt(total_pnl)}")
        _log("─" * 48)
        _log(f"✅ All 3 steps complete!  |  MCP tools: run_full_analysis ✓")
        _log("📲 Prefab UI refreshing in browser ...")
        with _lock:
            _csv_rows = rows
            _status   = "done"

    except Exception as e:
        _log(f"❌ Error: {e}")
        with _lock:
            _status = "error"


def build_html() -> str:
    gainers = sorted([h for h in _holdings if h["pnl"] > 0], key=lambda h: h["pnl"], reverse=True)
    losers  = sorted([h for h in _holdings if h["pnl"] <= 0], key=lambda h: h["pnl"])

    state = {
        "gainers":       gainers,
        "losers":        losers,
        "positions":     _positions,
        "total_pnl_str": _total_pnl_str,
        "csv_rows":      _csv_rows,
    }

    with PrefabApp(title="Zerodha Portfolio MCP", state=state, css_class="pt-0 px-6 pb-6 space-y-6") as app:

        # ── Holdings ─────────────────────────────────────────────────────────
        Heading("Holdings")
        if gainers:
            Text("Gainers ▲", css_class="text-green-500 font-semibold text-xs uppercase tracking-wide")
            with ForEach("gainers") as item:
                with Card(css_class="p-4 mb-2"):
                    with Column(css_class="gap-1"):
                        with Row(css_class="items-center gap-2"):
                            Text(f"{item.symbol}", bold=True)
                            Text(f"{item.type}", css_class="text-xs text-gray-400 bg-gray-800 px-2 py-0.5 rounded-full")
                        Text(f"{item.pnl_str}", css_class=f"{item.pnl_class}")
                        Text(f"₹{item.last_price}  ·  Avg ₹{item.avg_price}  ·  Qty {item.quantity}")
        if losers:
            Text("Losers ▼", css_class="text-red-500 font-semibold text-xs uppercase tracking-wide mt-4")
            with ForEach("losers") as item:
                with Card(css_class="p-4 mb-2"):
                    with Column(css_class="gap-1"):
                        with Row(css_class="items-center gap-2"):
                            Text(f"{item.symbol}", bold=True)
                            Text(f"{item.type}", css_class="text-xs text-gray-400 bg-gray-800 px-2 py-0.5 rounded-full")
                        Text(f"{item.pnl_str}", css_class=f"{item.pnl_class}")
                        Text(f"₹{item.last_price}  ·  Avg ₹{item.avg_price}  ·  Qty {item.quantity}")

        Separator()

        # ── Positions ────────────────────────────────────────────────────────
        Heading("Open Positions")
        with ForEach("positions") as item:
            with Card(css_class="p-4 mb-2"):
                with Column(css_class="gap-1"):
                    with Row(css_class="items-center gap-2"):
                        Text(f"{item.symbol}", bold=True)
                        Text(f"{item.product}", css_class="text-xs text-gray-400 bg-gray-800 px-2 py-0.5 rounded-full")
                    Text(f"{item.pnl_str}", css_class=f"{item.pnl_class}")
                    Text(f"₹{item.last_price}  ·  Avg ₹{item.avg_price}  ·  Qty {item.quantity}")

        Separator()

        # ── CSV Viewer ───────────────────────────────────────────────────────
        with Row(css_class="items-center justify-between"):
            Heading("portfolio.csv")
            Button("⬇  Download CSV", id="dl-btn", variant="outline", css_class="text-sm")
        if _csv_rows:
            with Card(css_class="p-4 bg-gray-950 font-mono text-sm space-y-1"):
                Text("symbol | type | qty | avg_price | last_price | pnl",
                     bold=True, css_class="text-gray-400 border-b border-gray-700 pb-1 mb-1")
                with ForEach("csv_rows") as row:
                    Text(f"{row.symbol} | {row.type} | {row.quantity} | "
                         f"{row.avg_price} | {row.last_price} | {row.pnl}",
                         css_class="text-gray-200")
        else:
            Text("No CSV yet — run analysis first.", css_class="text-gray-500 italic text-sm")

    html = app.html()

    # ── Inject header + live-log console as raw HTML ──────────────────────────
    pnl_color = "#4ade80" if _total_pnl_str.startswith("+") else "#f87171" if _total_pnl_str.startswith("-") else "#d1d5db"
    header_html = f"""
<div style="max-width:64rem;margin:0 auto;padding:2rem 2rem 0 2rem;font-family:system-ui,sans-serif">
  <div style="display:flex;justify-content:space-between;align-items:center;background:#1f2937;border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:1.5rem">
    <div>
      <h1 style="color:white;font-size:1.4rem;font-weight:700;margin:0">Zerodha Portfolio MCP</h1>
      <p style="color:{pnl_color};margin:4px 0 0;font-size:1rem;font-weight:600">Total P&amp;L: &#8377;{_total_pnl_str}</p>
    </div>
    <div style="display:flex;gap:0.75rem">
      <button id="run-btn" style="background:#2563eb;color:white;border:none;padding:0.5rem 1.25rem;border-radius:8px;cursor:pointer;font-size:0.9rem;font-weight:600">&#9654; Run Full Analysis</button>
      <button id="reset-btn" style="background:transparent;color:#d1d5db;border:1px solid #4b5563;padding:0.5rem 1.25rem;border-radius:8px;cursor:pointer;font-size:0.9rem">&#8635; Reset</button>
    </div>
  </div>
  <div style="background:#030712;border-radius:12px;padding:1rem;margin-bottom:1.5rem;min-height:140px;max-height:280px;overflow-y:scroll" id="pf-logs-wrap">
    <p style="color:#6b7280;font-size:0.7rem;font-family:monospace;margin:0 0 8px;text-transform:uppercase;letter-spacing:0.05em">Live Logs</p>
    <div id="pf-logs"></div>
  </div>
</div>"""
    # Find the Prefab mount div and prepend the header above it
    prefab_mount = '<div style="max-width:64rem;margin:0 auto;padding:2rem">'
    if prefab_mount in html:
        html = html.replace(
            prefab_mount,
            header_html + '\n<div style="max-width:64rem;margin:0 auto;padding:0 2rem 2rem">',
            1,
        )
    else:
        # Fallback: inject after <body>
        html = html.replace("<body>", "<body>" + header_html, 1)

    # ── Inject live-log JS ────────────────────────────────────────────────────
    js = """
<script>
(function() {
  var pollTimer = null;
  var wasRunning = false;

  function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  function updateLogs(logs) {
    var el = document.getElementById('pf-logs');
    if (!el) return;
    el.innerHTML = logs.map(function(l) {
      var color = l.startsWith('✅') || l.startsWith('📊') || l.startsWith('🔌') ? '#4ade80'
                : l.startsWith('❌') ? '#f87171'
                : l.startsWith('▶') ? '#60a5fa'
                : l.startsWith('─') ? '#374151'
                : '#d1d5db';
      return '<div style="font-family:monospace;font-size:12px;color:'+color+';padding:1px 0;white-space:pre">'+esc(l)+'</div>';
    }).join('');
    var wrap = document.getElementById('pf-logs-wrap');
    if (wrap) requestAnimationFrame(function(){ wrap.scrollTop = wrap.scrollHeight; });
  }

  function poll() {
    fetch('/logs')
      .then(function(r){ return r.json(); })
      .then(function(data) {
        updateLogs(data.logs);
        if (data.status === 'running') {
          wasRunning = true;
          pollTimer = setTimeout(poll, 250);
        } else if (data.status === 'done' && wasRunning) {
          wasRunning = false;
          // auto-download CSV
          var a = document.createElement('a');
          a.href = '/download'; a.download = 'portfolio.csv';
          document.body.appendChild(a); a.click(); document.body.removeChild(a);
          // reload dashboard after short delay
          setTimeout(function(){ window.location.reload(); }, 1200);
        } else {
          pollTimer = setTimeout(poll, 800);
        }
      })
      .catch(function(){ pollTimer = setTimeout(poll, 1000); });
  }

  function wireButtons() {
    // Run Full Analysis
    var runBtn = document.getElementById('run-btn');
    if (!runBtn) {
      // fallback: find by text
      document.querySelectorAll('button').forEach(function(b){
        if (b.textContent.trim().includes('Run Full Analysis')) runBtn = b;
      });
    }
    if (runBtn) {
      runBtn.addEventListener('click', function(e) {
        e.preventDefault(); e.stopImmediatePropagation();
        wasRunning = true;
        fetch('/run');
        if (pollTimer) clearTimeout(pollTimer);
        poll();
      }, true);
    }

    // Reset
    var resetBtn = document.getElementById('reset-btn');
    if (!resetBtn) {
      document.querySelectorAll('button').forEach(function(b){
        if (b.textContent.trim().includes('Reset')) resetBtn = b;
      });
    }
    if (resetBtn) {
      resetBtn.addEventListener('click', function(e) {
        e.preventDefault(); e.stopImmediatePropagation();
        fetch('/reset').then(function(){ window.location.reload(); });
      }, true);
    }

    // Download CSV
    var dlBtn = document.getElementById('dl-btn');
    if (!dlBtn) {
      document.querySelectorAll('button').forEach(function(b){
        if (b.textContent.trim().includes('Download CSV')) dlBtn = b;
      });
    }
    if (dlBtn) {
      dlBtn.addEventListener('click', function(e) {
        e.preventDefault(); e.stopImmediatePropagation();
        var a = document.createElement('a');
        a.href = '/download'; a.download = 'portfolio.csv';
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
      }, true);
    }
  }

  // Wire immediately + after short delay (for Prefab hydration)
  document.addEventListener('DOMContentLoaded', function() {
    wireButtons();
    poll();
  });
  setTimeout(wireButtons, 800);
  setTimeout(wireButtons, 2000);
  poll();
})();
</script>
"""
    html = html.replace("</body>", js + "\n</body>")
    return html


# ── Threaded HTTP server ──────────────────────────────────────────────────────
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        if path == "/run":
            threading.Thread(target=run_full_analysis, daemon=True).start()
            self._json({"ok": True})

        elif path == "/reset":
            reset()
            self._json({"ok": True})

        elif path == "/logs":
            with _lock:
                self._json({"logs": list(_logs), "status": _status})

        elif path == "/download":
            if os.path.exists(CSV_PATH):
                data = open(CSV_PATH, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", 'attachment; filename="portfolio.csv"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404, "No CSV yet")

        else:
            html = build_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


PORT = 8888
os.system(f"lsof -ti:{PORT} | xargs kill -9 2>/dev/null")
import time; time.sleep(1)

server = ThreadedHTTPServer(("localhost", PORT), Handler)
print(f"Dashboard → http://localhost:{PORT}")
webbrowser.open(f"http://localhost:{PORT}")
server.serve_forever()
