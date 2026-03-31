"""
Module 11 — Simple Profit/Loss Trading Dashboard (V6.3 Italian)
- Dry-Run Activity Tracking
- AI Transparent Thesis
"""
import os
import sys
import sqlite3
import json
import time
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.manager import MemoryManager

# --- AUTH & CONFIG ---
def load_env_file():
    """Manually parse .env to avoid dependency issues in WinSW."""
    env_vars = {}
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    parts = line.strip().split("=", 1)
                    if len(parts) == 2:
                        env_vars[parts[0].strip()] = parts[1].strip()
    return env_vars

ENV = load_env_file()
CTRL_USER = ENV.get("CONTROL_CENTER_USER")
CTRL_PASS = ENV.get("CONTROL_CENTER_PASSWORD")

if not CTRL_USER or not CTRL_PASS:
    print("CRITICAL: Auth credentials not set. FAIL-CLOSED.")
    sys.exit(1)

app = FastAPI(title="BOT AI V6.3 — Dashboard")
security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    """Validates against dedicated Control Center secrets."""
    if credentials.username != CTRL_USER or credentials.password != CTRL_PASS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# --- DATA EXTRACTION ---
def get_open_trades_count():
    """Query Freqtrade dry-run SQLite database for open trades."""
    db_path = Path(__file__).parent.parent / "tradesv3.dryrun.sqlite"
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM trades WHERE is_open = 1")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0

def get_bot_status():
    """Simplified bot status (Active, Paused, Stale)."""
    log_path = Path(__file__).parent.parent / "bin" / "V6-Freqtrade.err.log"
    if not log_path.exists():
        return "NON RILEVATO", "gray"
    
    mtime = log_path.stat().st_mtime
    elapsed = time.time() - mtime
    
    if elapsed < 120:  # 2 mins
        return "ATTIVO", "#10b981"
    elif elapsed < 600:  # 10 mins
        return "IN PAUSA", "#f59e0b"
    else:
        return "STALE (FERMO)", "#ef4444"

def get_last_logs(n=8):
    """Leggi le ultime N righe dal log di Freqtrade."""
    log_path = Path(__file__).parent.parent / "bin" / "V6-Freqtrade.err.log"
    if not log_path.exists():
        return ["Log non trovato."]
    try:
        with open(log_path, "rb") as f:
            lines = f.readlines()
            decoded = [l.decode('utf-8', errors='replace').strip() for l in lines[-n:] if l.strip()]
            return [l[-120:] for l in decoded]
    except Exception as e:
        return [f"Errore lettura log: {e}"]

# --- UI LAYER ---
@app.get("/", response_class=HTMLResponse)
def read_root(username: str = Depends(authenticate)):
    mgr = MemoryManager()
    eval_sum = mgr.compute_evaluation()
    
    # Capital and Equity logic
    starting_capital = 50.0
    try:
        config_path = Path(__file__).parent.parent / "config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            starting_capital = float(cfg.get("dry_run_wallet", 50.0))
    except: pass

    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    one_hour_ago = now - timedelta(hours=1)
    
    daily_pnl = 0.0
    equity = starting_capital
    
    for o in mgr._store.outcomes:
        try:
            o_ts = datetime.fromisoformat(o.get("timestamp_utc", ""))
            if o_ts > day_ago: daily_pnl += o.get("realized_pnl_pct", 0.0)
            equity += float(o.get("realized_pnl_abs", 0.0))
        except: continue
            
    total_pnl = eval_sum.avg_pnl_pct * eval_sum.total_executed if eval_sum.total_executed > 0 else 0.0
    open_trades = get_open_trades_count()
    status_text, status_color = get_bot_status()
    vmode = os.getenv("VALIDATION_MODE", "REAL").upper()
    last_logs = get_last_logs(4)

    # Decisions per hour
    decisions_last_hour = 0
    for d in mgr._store.decisions:
        try:
            d_ts = datetime.fromisoformat(d.get("timestamp_utc", ""))
            if d_ts > one_hour_ago:
                decisions_last_hour += 1
        except: pass
    
    # Process Timeline
    def it_fmt(d):
        ts = d.get("timestamp_utc", "Unknown").split("T")[-1][:8]
        asset = d.get("asset", "Unknown").split("/")[0]
        action = d.get("action", "hold").upper()
        thesis = d.get("thesis", "Analisi di mercato in corso...")
        
        emoji = "💤" if action == "HOLD" else "🚀" if action == "BUY" else "💰"
        act_ita = "MANTENIMENTO" if action == "HOLD" else "ACQUISTO" if action == "BUY" else "VENDITA"
        conf = d.get("confidence", 0)
        
        return f'''
        <div class="timeline-item">
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span>[{ts}] {emoji} <b>{act_ita} {asset}</b></span>
                <span style="color:#f59e0b; font-size:0.65rem;">Sicurezza AI: {conf}%</span>
            </div>
            <div style="background:#0f172a; padding:8px; border-left:3px solid #38bdf8; border-radius:4px; font-style:italic; color:#e2e8f0; font-size:0.7rem;">
                🧠 "{thesis}"
            </div>
        </div>
        '''

    timeline_items = mgr._store.decisions[-8:]
    timeline = [it_fmt(d) for d in reversed(timeline_items)]
    
    last_decision_ui = ""
    if timeline_items:
        ld = timeline_items[-1]
        ld_ts = ld.get("timestamp_utc", "Unknown").split("T")[-1][:8]
        ld_action = ld.get("action", "hold").upper()
        ld_asset = ld.get("asset", "Unknown")
        ld_thesis = ld.get("thesis", "")
        last_decision_ui = f'''
        <div style="background:rgba(56, 189, 248, 0.1); border: 1px solid #38bdf8; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
            <div style="font-size: 0.65rem; color:#38bdf8; font-weight:bold; letter-spacing:1px; margin-bottom:8px;">ULTIMA VALUTAZIONE AI (LIVE {ld_ts})</div>
            <div style="font-size: 0.85rem; margin-bottom:5px;"><b>{ld_asset}</b> &rsaquo; <span style="color:#f59e0b;">{ld_action}</span></div>
            <div style="font-size: 0.75rem; color:#cbd5e1; font-style:italic; line-height:1.4;">"{ld_thesis}"</div>
        </div>
        '''

    html_content = f"""
    <html>
        <head>
            <title>BOT AI V6.3</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: 'Inter', sans-serif; background: #0f172a; color: #f1f5f9; padding: 15px; margin: 0; }}
                h1 {{ font-size: 0.8rem; color: #64748b; text-transform: uppercase; text-align: center; margin: 15px 0; letter-spacing: 0.1em; }}
                
                .card {{ background: #1e293b; border-radius: 12px; border: 1px solid #334155; padding: 15px; margin-bottom: 15px; }}
                
                .status-line {{ display: flex; align-items: center; justify-content: space-between; font-size: 0.75rem; font-weight: bold; margin-bottom: 20px; padding: 0 5px; }}
                .status-dot {{ width: 10px; height: 10px; border-radius: 50%; background: {status_color}; margin-right: 8px; box-shadow: 0 0 10px {status_color}; {"animation: pulse 2s infinite;" if status_text == "ATTIVO" else ""} }}
                .status-pulse-text {{ font-size: 0.65rem; color: #38bdf8; margin-left: 10px; animation: flash 1.5s infinite; }}
                @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} 100% {{ opacity: 1; }} }}
                @keyframes flash {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} 100% {{ opacity: 1; }} }}
                
                .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }}
                .mini-card {{ background: #1e293b; border: 1px solid #334155; padding: 12px; border-radius: 8px; text-align:center; }}
                .label {{ font-size: 0.6rem; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px; }}
                .val {{ font-size: 1.2rem; font-weight: bold; }}
                .val-sub {{ font-size: 0.6rem; color: #64748b; margin-top:2px; }}

                .section-title {{ font-size: 0.75rem; font-weight: bold; color: #38bdf8; margin: 20px 0 10px 5px; text-transform: uppercase; }}
                
                .timeline-item {{ font-size: 0.75rem; padding: 12px 0; border-bottom: 1px solid #334155; }}
                .timeline-item:last-child {{ border-bottom: none; }}
                
                .log-feed {{ background: #000; color: #4ade80; font-family: 'Courier New', monospace; font-size: 0.6rem; padding: 12px; border-radius: 8px; line-height: 1.4; border: 1px solid #4ade8033; overflow-x: auto; }}
                
                .heartbeat {{ height: 2px; background: #334155; position: relative; overflow: hidden; margin: 0 -15px 20px -15px; }}
                .heartbeat-bar {{ position: absolute; height: 100%; width: 30%; background: linear-gradient(90deg, transparent, #38bdf8, transparent); animation: sweep {"2s" if status_text == "ATTIVO" else "10s"} infinite linear; }}
                @keyframes sweep {{ from {{ left: -30%; }} to {{ left: 100%; }} }}
            </style>
        </head>
        <body>
            <h1>Motore AI di Tony — Dry-Run Live</h1>
            <div class="heartbeat"><div class="heartbeat-bar"></div></div>

            <div class="status-line">
                <div style="display: flex; align-items:center;">
                    <div class="status-dot"></div> {status_text}
                    {'''<span class="status-pulse-text">Analisi mercati in corso...</span>''' if status_text == "ATTIVO" else ""}
                </div>
                <div style="color: #64748b;">{vmode}</div>
            </div>

            {last_decision_ui}

            <div class="grid">
                <div class="mini-card">
                    <div class="label">Capitale Corrente</div>
                    <div class="val" style="color: #f1f5f9;">${equity:.2f}</div>
                    <div class="val-sub">Base: ${starting_capital:.2f}</div>
                </div>
                <div class="mini-card">
                    <div class="label">Operazioni Attive</div>
                    <div class="val" style="color: #10b981;">{open_trades}</div>
                    <div class="val-sub">Lavori in corso</div>
                </div>
                <div class="mini-card">
                    <div class="label">Attività AI (1h)</div>
                    <div class="val" style="color: #38bdf8;">{decisions_last_hour}</div>
                    <div class="val-sub">Analisi elaborate</div>
                </div>
                <div class="mini-card">
                    <div class="label">Profitto Totale</div>
                    <div class="val" style="color: {'#10b981' if total_pnl >= 0 else '#ef4444'};">{total_pnl:+.1f}%</div>
                    <div class="val-sub">{eval_sum.total_executed} conclusi</div>
                </div>
            </div>

            <div class="section-title">Timeline Pensiero AI</div>
            <div class="card" style="padding: 5px 15px;">
                {''.join(timeline) if timeline else '<div style="font-size:0.7rem; color:#64748b; padding: 20px; text-align:center;">IL BOT STA ANALIZZANDO... <br> In attesa della prima decisione AI.</div>'}
            </div>

            <div class="section-title">Attività Tecnica Recente</div>
            <div class="log-feed">
                {'<br>'.join(last_logs)}
            </div>

            <div style="margin-top: 30px; font-size: 0.6rem; color: #475569; text-align: center;">
                Ultimo refresh: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC
            </div>

            <script>setTimeout(() => window.location.reload(), 15000);</script>
        </body>
    </html>
    """
    return html_content

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8086)
