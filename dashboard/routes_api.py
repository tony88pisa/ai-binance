"""
V9.0 — Unified Dashboard API
All endpoints the frontend needs, in one file.
"""
import json
from pathlib import Path
from fastapi import APIRouter
from storage.repository import Repository
from scheduler.session_manager import current_mode
from services.exchange_executor import ExchangeExecutor

router = APIRouter(prefix="/api")

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
DEFAULT_BUDGET = 50.0


@router.get("/state")
def get_state():
    """Full system state: daemon, wallet, counts."""
    repo = Repository()
    state = repo.get_service_state("daemon")
    try:
        sj = json.loads(state.get("state_json", "{}"))
    except Exception:
        sj = {}

    wallet = sj.get("wallet_eur", DEFAULT_BUDGET)
    pnl_eur = round(wallet - DEFAULT_BUDGET, 2)
    pnl_pct = round((pnl_eur / DEFAULT_BUDGET) * 100, 2) if DEFAULT_BUDGET else 0

    # Counts
    with repo._conn() as conn:
        open_cnt = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE status='OPEN'"
        ).fetchone()[0]
        closed_cnt = conn.execute(
            "SELECT COUNT(*) FROM trade_outcomes"
        ).fetchone()[0]
        total_decisions = conn.execute(
            "SELECT COUNT(*) FROM decisions"
        ).fetchone()[0]

    # Real-time exchange balance
    executor = ExchangeExecutor()
    testnet_balance = round(executor.get_balance("USDT"), 2) if executor.enabled else 0.0

    return {
        "mode": sj.get("mode", current_mode()),
        "hb": state.get("last_heartbeat", "N/A"),
        "status": "ONLINE" if state.get("last_heartbeat", "N/A") != "N/A" else "OFFLINE",
        "wallet_initial": DEFAULT_BUDGET,
        "wallet_current": round(wallet, 2),
        "pnl_eur": pnl_eur,
        "pnl_pct": pnl_pct,
        "open_trades": open_cnt,
        "closed_trades": closed_cnt,
        "total_decisions": total_decisions,
        "testnet_balance": testnet_balance,
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
        })
    return out


@router.get("/history")
def get_history():
    """Closed trades with outcomes."""
    repo = Repository()
    return repo.get_history(limit=20)


@router.get("/learning")
def get_learning():
    """Lab evolution stats."""
    repo = Repository()
    with repo._conn() as conn:
        # Filter legacy/corrupted data
        outcome_cnt = conn.execute("""
            SELECT COUNT(*) FROM trade_outcomes o 
            JOIN decisions d ON o.decision_id = d.id 
            WHERE d.entry_price > 0 AND ABS(o.realized_pnl_pct) < 5.0
        """).fetchone()[0]
        
        wins = conn.execute("""
            SELECT COUNT(*) FROM trade_outcomes o 
            JOIN decisions d ON o.decision_id = d.id 
            WHERE o.was_profitable = 1 AND d.entry_price > 0 AND ABS(o.realized_pnl_pct) < 10.0
        """).fetchone()[0]
        
        winrate = round((wins / outcome_cnt) * 100, 1) if outcome_cnt > 0 else 0
        
        total_pnl = conn.execute("""
            SELECT SUM(o.realized_pnl_pct) FROM trade_outcomes o 
            JOIN decisions d ON o.decision_id = d.id 
            WHERE d.entry_price > 0 AND ABS(o.realized_pnl_pct) < 5.0
        """).fetchone()[0] or 0

        # Per-asset stats sanitized
        asset_stats = conn.execute("""
            SELECT d.asset,
                   COUNT(*) as cnt,
                   SUM(CASE WHEN o.was_profitable THEN 1 ELSE 0 END) as wins,
                   ROUND(SUM(o.realized_pnl_pct)*100, 2) as total_pnl_pct
            FROM trade_outcomes o JOIN decisions d ON o.decision_id = d.id
            WHERE d.entry_price > 0 AND ABS(o.realized_pnl_pct) < 5.0
            GROUP BY d.asset ORDER BY total_pnl_pct DESC
        """).fetchall()
        asset_stats = [dict(r) for r in asset_stats]

    skills = repo.list_skill_candidates()
    return {
        "outcomes_total": outcome_cnt,
        "winrate": winrate,
        "total_pnl_pct": round(total_pnl * 100, 2),
        "skill_candidates": len(skills),
        "skills": [{"id": s["skill_id"], "name": s["name"], "status": s["status"]} for s in skills[:10]],
        "asset_performance": asset_stats,
        "lab_mode": "ISOLATED",
        "promotion_mode": "MANUAL ONLY",
    }


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
        "supervisor": "supervisor.log"
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
