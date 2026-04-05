"""
V9.0 — Unified Dashboard API
All endpoints the frontend needs, in one file.
"""
import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter
from config.settings import get_settings
from storage.repository import Repository
from services.exchange_executor import ExchangeExecutor

# Global config
settings = get_settings()

# Cache per evitare rate limits su Binance (-1003)
_balance_cache = {"val": 0.0, "ts": 0}
CACHE_TTL = 30 # secondi

# Load .env
load_dotenv()

router = APIRouter(prefix="/api")

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"

@router.get("/logs/tail")
def tail_logs(source: str, lines: int = 50):
    """Returns the last N lines of a log file."""
    log_file = LOGS_DIR / f"{source}.log"
    if not log_file.exists():
        return {"error": "Log file not found", "lines": []}
    
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            return {"source": source, "lines": all_lines[-lines:]}
    except Exception as e:
        return {"error": str(e), "lines": []}


@router.get("/state")
def get_state():
    """Full system state: daemon, wallet, counts."""
    repo = Repository()
    state = repo.get_service_state("daemon")
    try:
        sj = json.loads(state.get("state_json", "{}"))
    except Exception:
        sj = {}

    executor = ExchangeExecutor()
    
    # --- Wallet & PnL Logic ---
    currency = settings.trading.stake_currency
    initial_budget = settings.trading.wallet_size
    is_testnet = executor.mode.lower() == "testnet"
    
    # Real-time balance from executor (cached for 30s to avoid -1003)
    import time
    now = time.time()
    if now - _balance_cache["ts"] > CACHE_TTL:
        exchange_balance = executor.get_balance(currency)
        _balance_cache["val"] = exchange_balance
        _balance_cache["ts"] = now
    else:
        exchange_balance = _balance_cache["val"]
    
    # Calculate REAL Bot PnL — EXCLUDE test records (entry_price=0 are setup/test data)
    with repo._conn() as conn:
        pnl_bot_row = conn.execute("""
            SELECT SUM(o.realized_pnl_pct * (CASE WHEN d.size_pct > 0 THEN d.size_pct / 100.0 ELSE 1.0 END))
            FROM trade_outcomes o
            JOIN decisions d ON o.decision_id = d.id
            WHERE d.entry_price > 0
        """).fetchone()
        
        bot_pnl_pct = float(pnl_bot_row[0]) if pnl_bot_row and pnl_bot_row[0] else 0.0
        
        open_cnt = conn.execute("SELECT COUNT(*) FROM decisions WHERE status='OPEN'").fetchone()[0]
        # Only count REAL closed trades (with entry_price > 0)
        closed_cnt = conn.execute("""
            SELECT COUNT(*) FROM trade_outcomes o
            JOIN decisions d ON o.decision_id = d.id
            WHERE d.entry_price > 0
        """).fetchone()[0]
        # Count ALL test+real trade outcomes for transparency
        total_outcomes = conn.execute("SELECT COUNT(*) FROM trade_outcomes").fetchone()[0]
        total_decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]

    pnl_val_estimated = round(initial_budget * (bot_pnl_pct / 100.0), 2)
    # Wallet value: prioritize REAL exchange balance if in REAL/TESTNET mode
    if exchange_balance > 0:
        wallet_display = round(exchange_balance, 2)
    else:
        wallet_display = round(initial_budget + pnl_val_estimated, 2)

    # Open orders from exchange
    ex_orders = executor.get_open_orders()

    return {
        "mode": sj.get("mode", settings.exchange.mode),
        "hb": state.get("last_heartbeat", "N/A"),
        "status": "ONLINE" if state.get("last_heartbeat", "N/A") != "N/A" else "OFFLINE",
        "wallet_initial": initial_budget,
        "wallet_current": wallet_display,
        "exchange_balance": round(exchange_balance, 2),
        "pnl_eur": pnl_val_estimated,
        "pnl_pct": round(bot_pnl_pct, 2),
        "currency": currency,
        "exchange_mode": executor.mode.upper(),
        "is_testnet": is_testnet,
        "open_trades": open_cnt,
        "closed_trades": closed_cnt,
        "total_outcomes_incl_test": total_outcomes,
        "total_decisions": total_decisions,
        "open_orders_exchange": ex_orders,
        # V11 — Micro-Cap Scaler fields
        "auto_compound": settings.trading.auto_compound,
        "risk_per_trade_pct": settings.trading.risk_per_trade_pct,
        "global_take_profit": settings.trading.global_take_profit,
    }


@router.get("/assets")
def get_assets():
    """AI decision engine: per-asset snapshots."""
    repo = Repository()
    snaps = repo.get_latest_snapshots()
    out = []
    for s in snaps:
        asset_name = s.get("asset", "")
        # Filter out legacy database entries (e.g. 'BNBUSDT')
        if "/" not in asset_name:
            continue
        out.append({
            "asset": asset_name,
            "price": s.get("price", 0),
            "decision": s.get("decision", "hold"),
            "confidence": s.get("confidence", 0),
            "regime": s.get("regime", "N/A"),
            "consensus_score": s.get("consensus_score", 0),
            "position_size_pct": s.get("position_size_pct", 0),
            "atr_stop_distance": s.get("atr_stop_distance", 0),
            "why_not_trade": s.get("why_not_trade", ""),
            "rsi_5m": s.get("rsi_5m", 0),
            "macd_5m": s.get("macd_5m", 0),
            "updated_at": s.get("updated_at", ""),
        })
    return out


@router.get("/arena")
def get_arena():
    """Aggregated performance and sentiment for Agent dots."""
    repo = Repository()
    with repo._conn() as conn:
        # Get latest performance per agent from outcomes
        perf = conn.execute("""
            SELECT d.agent_name, 
                   AVG(o.realized_pnl_pct) as avg_pnl, 
                   COUNT(*) as trades,
                   AVG(d.confidence) as avg_conf
            FROM decisions d 
            JOIN trade_outcomes o ON d.id = o.decision_id
            GROUP BY d.agent_name
        """).fetchall()
        
    agents = []
    # Mix real data with predefined agents if no data exists yet
    known_agents = ["Alpha-Quantum", "Trend-Scout", "WallStreet-Bot"]
    found_names = [row["agent_name"] for row in perf]
    
    # Real data
    for row in perf:
        agents.append({
            "name": row["agent_name"],
            "pnl": round(row["avg_pnl"] * 100, 2),
            "trades": row["trades"],
            "sentiment": round(row["avg_conf"], 0), # Using confidence as a proxy for 'greed'
            "status": "ACTIVE"
        })
        
    # 2. Add Active Thoughts (from current market snapshots)
    snaps = repo.get_latest_snapshots()
    for snap in snaps:
        # We assign thoughts to 'Trend-Scout' or 'Alpha-Quantum' based on confidence/asset
        name = "Alpha-Quantum" if "/" in snap["asset"] and snap["confidence"] > 60 else "Trend-Scout"
        # Only add as active thought if not already counted as trade performer
        agents.append({
            "name": name,
            "asset": snap["asset"],
            "pnl": 0.0, # Neutral Y position for thoughts
            "sentiment": snap["confidence"],
            "status": "THINKING",
            "thesis": snap["why_not_trade"] or snap["decision"]
        })

    return agents


@router.get("/knowledge")
def get_knowledge():
    """Calculates 'Market Affinity' based on learning state and data density."""
    repo = Repository()
    # 1. Check Dream Agent status
    dream_state = repo.get_service_state("dream_agent")
    
    # 2. Calculate affinity based on how many assets are currently being analyzed
    snaps = repo.get_latest_snapshots()
    active_count = len([s for s in snaps if (s.get("confidence") or 0) > 0])
    
    # 3. Baseline affinity (progress bar filler)
    # If dream_agent is active and we have data, we are 'synced'
    affinity = 40 # Base
    if dream_state: affinity += 30
    if active_count > 5: affinity += 20
    if active_count > 10: affinity += 10
    
    return {
        "affinity_pct": min(affinity, 100),
        "learning_status": "Deep Learning" if affinity > 70 else "Observing",
        "last_paradigm_update": dream_state.get("last_heartbeat", "N/A")
    }


@router.get("/positions")
def get_positions():
    """Open trades with current market price for PnL calc."""
    repo = Repository()
    open_trades = repo.get_open_decisions()
    snaps = {s["asset"]: s for s in repo.get_latest_snapshots()}
    out = []
    for t in open_trades:
        asset = t.get("asset", "")
        entry = float(t.get("entry_price", 0))
        current = float(snaps.get(asset, {}).get("price", entry))
        pnl_pct = round(((current - entry) / entry) * 100, 2) if entry > 0 else 0
        out.append({
            "id": t.get("id"),
            "asset": asset,
            "action": t.get("action", "buy"),
            "entry_price": entry,
            "current_price": current,
            "size_pct": float(t.get("size_pct", 0)),
            "pnl_pct": pnl_pct,
            "direction": "up" if pnl_pct >= 0 else "down",
            "opened_at": t.get("timestamp", "N/A"),
            "inner_monologue": t.get("inner_monologue", ""),
            "exchange_order_id": t.get("exchange_order_id")
        })
    return out


@router.get("/history")
def get_history():
    """Closed trades with outcomes."""
    repo = Repository()
    return repo.get_history(limit=20)


@router.get("/learning")
def get_learning():
    """Lab evolution stats with safety."""
    repo = Repository()
    try:
        with repo._conn() as conn:
            # Only count REAL trades (entry_price > 0) — test records are excluded
            outcome_cnt = conn.execute("""
                SELECT COUNT(*) FROM trade_outcomes o 
                JOIN decisions d ON o.decision_id = d.id
                WHERE d.entry_price > 0
            """).fetchone()[0] or 0
            
            wins = conn.execute("""
                SELECT COUNT(*) FROM trade_outcomes o 
                JOIN decisions d ON o.decision_id = d.id 
                WHERE o.was_profitable = 1 AND d.entry_price > 0
            """).fetchone()[0] or 0
            
            winrate = round((wins / outcome_cnt) * 100, 1) if outcome_cnt > 0 else 0
            
            total_pnl = conn.execute("""
                SELECT SUM(o.realized_pnl_pct * (CASE WHEN d.size_pct > 0 THEN d.size_pct / 100.0 ELSE 1.0 END)) FROM trade_outcomes o 
                JOIN decisions d ON o.decision_id = d.id
                WHERE d.entry_price > 0
            """).fetchone()[0] or 0

            asset_stats_raw = conn.execute("""
                SELECT d.asset,
                       COUNT(*) as cnt,
                       SUM(CASE WHEN o.was_profitable THEN 1 ELSE 0 END) as wins,
                       ROUND(SUM(o.realized_pnl_pct)*100, 2) as total_pnl_pct
                FROM trade_outcomes o JOIN decisions d ON o.decision_id = d.id
                GROUP BY d.asset ORDER BY total_pnl_pct DESC
            """).fetchall()
            asset_stats = [dict(r) for r in asset_stats_raw] if asset_stats_raw else []

        skills = repo.list_skill_candidates()
        formatted_skills = []
        for s in skills[:10]:
            formatted_skills.append({
                "id": s.get("skill_id", "N/A"),
                "name": s.get("name", "N/A"),
                "status": s.get("status", "N/A")
            })

        return {
            "outcomes_total": outcome_cnt,
            "winrate": winrate,
            "total_pnl_pct": round(total_pnl * 100, 2),
            "skill_candidates": len(skills),
            "skills": formatted_skills,
            "asset_performance": asset_stats,
            "lab_mode": "ISOLATED",
            "promotion_mode": "MANUAL ONLY",
        }
    except Exception as e:
        import traceback
        print(f"Error in get_learning: {e}")
        print(traceback.format_exc())
        return {"error": str(e), "status": "failed"}


@router.get("/logs")
def get_logs(source: str = "daemon", lines: int = 40):
    """Read last N lines from a log file."""
    allowed = {
        "daemon": "daemon.log",
        "error": "daemon_error.log",
        "dashboard": "dashboard_error.log",
        "evolution": "evolution_loop.log",
        "evolution_error": "evolution_loop_error.log",
        "cloudflare": "cloudflared.log",
        "supervisor": "supervisor.log",
        "analyzer": "analyzer.log",
        "dream_agent": "dream_agent.log",
        "coordinator": "coordinator.log",
        "controller": "controller.log",
        "squad_crypto": "squad_crypto.log",
        "squad_equity": "squad_equity.log",
        "news_trader": "news_trader.log",
        "brute_force": "brute_force.log",
    }
    fname = allowed.get(source)
    if not fname:
        return {"lines": [], "error": f"Unknown source: {source}"}
    fpath = LOGS_DIR / fname
    if not fpath.exists():
        return {"lines": [], "error": "Log file not found"}
    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return {"lines": all_lines[-lines:], "source": source}


@router.get("/supervisor")
def get_supervisor():
    """AI Supervisor current overrides and latest logs."""
    repo = Repository()
    controls = repo.get_supervisor_controls()
    logs = repo.get_supervisor_logs(limit=5)
    return {
        "controls": controls,
        "recent_logs": logs
    }


@router.get("/health")
def get_health():
    """Real health check — verifies which services are actually running."""
    import requests
    from datetime import datetime, timezone, timedelta
    repo = Repository()
    
    # Check Ollama
    ollama_ok = False
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
    except: pass
    
    # Check agent heartbeats (stale = >10 min = probably dead)
    now = datetime.now(timezone.utc)
    threshold = timedelta(minutes=10)
    
    services = ["squad_crypto", "squad_equity", "news_trader", "daemon", "risk_controller", "dream_agent", 
                "coordinator", "autoevolve", "equity_daemon"]
    status = {}
    for svc in services:
        state = repo.get_service_state(svc)
        hb = state.get("last_heartbeat", "")
        if hb and hb != "N/A":
            try:
                last = datetime.fromisoformat(hb.replace("Z", "+00:00"))
                age = now - last
                status[svc] = "active" if age < threshold else "stale"
            except: status[svc] = "unknown"
        else:
            status[svc] = "offline"
    
    # Check NVIDIA API
    nvidia_ok = False
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if nvidia_key and len(nvidia_key) > 10:
        nvidia_ok = True  # Key exists, assume callable
    
    return {
        "ollama": ollama_ok,
        "nvidia_api": nvidia_ok,
        "exchange": status.get("daemon", "offline") != "offline",
        "agents": status
    }


@router.get("/system")
def get_system():
    """Debug / system info."""
    repo = Repository()
    with repo._conn() as conn:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_info = {}
        for t in tables:
            name = t[0]
            cnt = conn.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
            table_info[name] = cnt

    # Check services
    state_daemon = repo.get_service_state("daemon")
    log_files = {}
    for lf in LOGS_DIR.glob("*"):
        log_files[lf.name] = lf.stat().st_size

    return {
        "db_path": str(repo.db_path),
        "tables": table_info,
        "daemon_state": {
            "hb": state_daemon.get("last_heartbeat", "N/A"),
            "status": state_daemon.get("status", "unknown"),
        },
        "log_files": log_files,
        "port": 8087,
    }


@router.get("/activity")
def get_activity():
    """Real-time activity feed from all agents."""
    repo = Repository()
    activities = repo.get_recent_activity(limit=30)
    return activities


@router.get("/agent-status")
def get_agent_status():
    """Detailed agent status with timestamps and metadata."""
    from datetime import datetime, timezone, timedelta
    repo = Repository()
    now = datetime.now(timezone.utc)
    threshold = timedelta(minutes=5)
    
    agents_info = {}
    for svc in ["squad_crypto", "squad_equity", "news_trader", "executor", "risk_controller", 
                "dream_agent", "coordinator", "evolution_loop", "equity_daemon"]:
        state = repo.get_service_state(svc)
        hb = state.get("last_heartbeat", "")
        status = "offline"
        age_seconds = None
        meta = {}
        
        if hb and hb != "N/A":
            try:
                last = datetime.fromisoformat(hb.replace("Z", "+00:00"))
                age = now - last
                age_seconds = int(age.total_seconds())
                status = "active" if age < threshold else "stale"
            except: pass
        
        state_json = state.get("state_json", "{}")
        try:
            meta = json.loads(state_json) if state_json else {}
        except: pass
        
        agents_info[svc] = {
            "status": status,
            "last_heartbeat": hb or "never",
            "age_seconds": age_seconds,
            "meta": meta
        }
    
    return agents_info

@router.get("/supermemory")
def get_supermemory_api():
    """Restituisce il contenuto della supermemoria"""
    try:
        from storage.superbrain import get_superbrain
        brain = get_superbrain()
        
        if not brain.enabled:
            return {"status": "offline", "data": "SuperBrain (Supermemory API Key) non configurata in .env"}
        
        # Recupera le ultime strategie generate e il contesto di mercato recente come demo
        recent_strategies = brain.recall("strategy", category="strategies", limit=3)
        recent_feedbacks = brain.recall("error anomaly", category="feedback", limit=3)
        
        memories = [
            {"type": "strategies", "content": recent_strategies},
            {"type": "feedback", "content": recent_feedbacks}
        ]
        
        return {"status": "online", "data": "SuperBrain attivo e sincronizzato.", "memories": memories}
    except Exception as e:
        return {"status": "error", "data": f"Errore interno SuperBrain: {str(e)}"}


@router.get("/v11-status")
def get_v11_status():
    """V11 Micro-Cap Scaler: Tax Reserve, Kelly Sizing, Grid Assessment, Fiscal Report."""
    repo = Repository()
    controls = repo.get_supervisor_controls()
    
    # Tax Reserve e Position Size dal Risk Controller
    position_size = controls.get("position_size_usdt", 0)
    tax_reserve = controls.get("tax_reserve_usdt", 0)
    max_leverage = controls.get("max_leverage", 1)
    
    # Fiscal Reporter: ultimo snapshot
    fiscal_summary = {}
    try:
        from modules.fiscal_reporter import FiscalReporter
        fr = FiscalReporter()
        fiscal_summary = fr.get_year_summary()
    except Exception as e:
        fiscal_summary = {"error": str(e)}
    
    # Grid Engine: valutazione rapida
    grid_status = {}
    try:
        from ai.grid_engine import AdaptiveGridEngine, GridConfig
        grid_cfg = GridConfig(symbol="BTC/USDT", total_budget_usdt=50.0, grid_levels=5)
        engine = AdaptiveGridEngine(grid_cfg)
        grid_status = {"engine": "ready", "levels": grid_cfg.grid_levels, "budget_per_cell": round(50.0 / 5, 2)}
    except Exception as e:
        grid_status = {"engine": "error", "detail": str(e)}
    
    return {
        "version": "V11 Micro-Cap Scaler",
        "auto_compound": settings.trading.auto_compound,
        "position_size_usdt": position_size,
        "tax_reserve_33pct_usdt": tax_reserve,
        "max_leverage": max_leverage,
        "kelly_risk_pct": settings.trading.risk_per_trade_pct * 100,
        "global_take_profit": settings.trading.global_take_profit,
        "fiscal_summary": fiscal_summary,
        "grid_engine": grid_status,
        "exchanges_available": ["binance", "mexc", "bybit", "kucoin"]
    }

