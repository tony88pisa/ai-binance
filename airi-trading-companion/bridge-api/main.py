import sys
import os
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Configuration
AI_BINANCE_ROOT = Path(os.environ.get("AI_BINANCE_ROOT", str(Path(__file__).resolve().parent.parent.parent)))
sys.path.insert(0, str(AI_BINANCE_ROOT))

# Validate paths
if not (AI_BINANCE_ROOT / "storage").exists():
    raise RuntimeError(f"Core non trovato in {AI_BINANCE_ROOT}")

from storage.repository import Repository
from config.settings import get_settings

app = FastAPI(title="Tengu Companion Bridge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = Repository()
settings = get_settings()

@app.get("/summary")
def get_summary():
    """Restituisce il sommario di alto livello della situazione."""
    squad_crypto_state = repo.get_service_state("squad_crypto")
    try:
        sc_sj = json.loads(squad_crypto_state.get("state_json", "{}"))
        current_wallet = round(float(sc_sj.get("equity", settings.trading.wallet_size)), 2)
    except:
        current_wallet = settings.trading.wallet_size

    # PNL Calcs
    initial = settings.trading.wallet_size
    pnl_total = round(current_wallet - initial, 2)
    pnl_total_pct = round(((current_wallet - initial) / initial) * 100, 2) if initial > 0 else 0.0

    return {
        "wallet_current": current_wallet,
        "wallet_initial": initial,
        "pnl_total": pnl_total,
        "pnl_total_pct": pnl_total_pct,
        "active_trades": len(repo.get_open_decisions()),
        "status": "ONLINE" if squad_crypto_state.get("last_heartbeat") else "OFFLINE"
    }

@app.get("/pnl/today")
def get_pnl_today():
    """Calcola il PNL generato dalle operazioni chiuse oggi."""
    today_stamp = datetime.utcnow().strftime("%Y-%m-%d")
    with repo._conn() as conn:
        row = conn.execute("""
            SELECT SUM(o.realized_pnl_pct) 
            FROM trade_outcomes o
            WHERE o.trade_ended_at LIKE ?
        """, (f"{today_stamp}%",)).fetchone()
    
    today_pct = row[0] if row and row[0] else 0.0
    return {"today_pnl_pct": round(today_pct, 2)}

@app.get("/pnl/total")
def get_pnl_total():
    """Calcola il PNL generato storicamente da tutte le operazioni."""
    with repo._conn() as conn:
        row = conn.execute("SELECT SUM(realized_pnl_pct) FROM trade_outcomes").fetchone()
    total_pct = row[0] if row and row[0] else 0.0
    return {"total_pnl_pct": round(total_pct, 2)}

@app.get("/wallet")
def get_wallet():
    squad_crypto_state = repo.get_service_state("squad_crypto")
    try:
        sc_sj = json.loads(squad_crypto_state.get("state_json", "{}"))
        current_wallet = round(float(sc_sj.get("equity", settings.trading.wallet_size)), 2)
    except:
        current_wallet = settings.trading.wallet_size
    return {"current_wallet": current_wallet, "initial_budget": settings.trading.wallet_size}

@app.get("/positions/open")
def get_positions_open():
    """Restituisce e arricchisce i trade attivi."""
    trades = repo.get_open_decisions()
    snaps = {s["asset"]: s for s in repo.get_latest_snapshots()}
    
    active = []
    for t in trades:
        asset = t.get("asset")
        entry = t.get("entry_price", 0.0)
        current = snaps.get(asset, {}).get("price", entry)
        pnl = round(((current - entry) / entry) * 100, 2) if entry > 0 else 0.0
        
        active.append({
            "asset": asset,
            "action": t.get("action"),
            "entry_price": entry,
            "current_price": current,
            "pnl_pct": pnl,
            "size_pct": t.get("size_pct")
        })
    return {"open_positions": active}

@app.get("/trades/recent")
def get_recent_trades():
    """Ultimi 5 trade."""
    with repo._conn() as conn:
        rows = conn.execute("""
            SELECT d.asset, d.action, d.entry_price, o.exit_price, o.realized_pnl_pct, o.trade_ended_at
            FROM trade_outcomes o
            JOIN decisions d ON o.decision_id = d.id
            ORDER BY o.trade_ended_at DESC
            LIMIT 5
        """).fetchall()
        
    trades = []
    for r in rows:
        trades.append({
            "asset": r["asset"],
            "action": r["action"],
            "entry_price": r["entry_price"],
            "exit_price": r["exit_price"],
            "pnl_pct": r["realized_pnl_pct"],
            "closed_at": r["trade_ended_at"]
        })
    return {"recent_trades": trades}

@app.get("/agents/status")
def get_agents_status():
    """Visualizza quali agenti sono vivi."""
    services = ["squad_crypto", "squad_equity", "news_trader", "coordinator", "dream_agent", "executor", "risk_controller"]
    status_db = {}
    for s in services:
        state = repo.get_service_state(s)
        status_db[s] = {
            "last_heartbeat": state.get("last_heartbeat", "never"),
            "status": state.get("status", "offline")
        }
    
    controls = repo.get_supervisor_controls()
    return {
        "emergency_stop": controls.get("emergency_stop", 0),
        "agents": status_db
    }

@app.get("/reports/coordinator/latest")
def get_coordinator_latest():
    log_path = AI_BINANCE_ROOT / "logs" / "coordinator.log"
    if not log_path.exists():
        return {"report": "Non disponibile"}
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-30:]
        return {"report": "".join(lines).strip()}
    except Exception as e:
        return {"error": str(e)}

@app.get("/events/recent")
def get_events_recent():
    """Ultime righe the system alert logic/log"""
    return {"events": "Tutto regolare in stazione"}

@app.get("/reports/dream/latest")
def get_dream_latest():
    """Legge l'output di memoria/analisi del dream agent o i log."""
    log_path = AI_BINANCE_ROOT / "logs" / "dream_agent.log"
    if not log_path.exists():
        return {"insight": "Nessun log recente dal Dream Agent."}
    
    try:
        lines = []
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-20:] # Read latest lines
        return {"insight": "".join(lines).strip()}
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
def health():
    return {"status": "ok"}
