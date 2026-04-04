"""
MCP Server for AI Trading Bot.
Exposes tools via the Anthropic Model Context Protocol (SSE transport).
Port: 8089

Tools:
  - get_trading_status: Wallet, PnL, open trades, supervisor controls.
  - trigger_emergency_stop: Force-halt new buys with a reason.
  - resume_trading: Resume trading after emergency stop.
  - read_agent_memory: Read the risk policy & asset memory files.
  - append_agent_insight: Append a new learning to risk policy.
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP
from storage.repository import Repository
from storage.memory_manager import MemoryManager
from config.settings import get_settings

settings = get_settings()

mcp = FastMCP(
    "AI Trading Bot",
    instructions="MCP server for a Binance crypto trading bot. Use tools to inspect status, manage risk, and interact with agent memory.",
    host="0.0.0.0",
    port=8089,
)

def _get_repo():
    return Repository()

def _get_mm():
    return MemoryManager(str(PROJECT_ROOT))


@mcp.tool()
def get_trading_status() -> str:
    """Get the current trading bot status: wallet balance, PnL, open trades, supervisor controls, and agent heartbeats."""
    repo = _get_repo()
    
    # Wallet & controls
    controls = repo.get_supervisor_controls()
    
    # Open trades
    open_trades = repo.get_open_decisions()
    trades_summary = []
    for t in open_trades:
        trades_summary.append({
            "asset": t["asset"],
            "entry_price": t.get("entry_price", 0),
            "confidence": t.get("confidence", 0),
            "regime": t.get("regime", "UNKNOWN"),
        })
    
    # Recent outcomes
    history = repo.get_history(limit=10)
    wins = sum(1 for h in history if h.get("was_profitable"))
    total = len(history)
    winrate = (wins / total * 100) if total > 0 else 0
    
    # Service heartbeats
    services = {}
    for svc in ["executor", "analyzer", "controller", "dashboard"]:
        state = repo.get_service_state(svc)
        if state:
            services[svc] = {
                "status": state.get("status", "unknown"),
                "last_heartbeat": state.get("last_heartbeat", "N/A"),
            }
    
    # Latest market snapshots
    snapshots = repo.get_latest_snapshots()
    markets = []
    for s in snapshots:
        markets.append({
            "asset": s["asset"],
            "price": s["price"],
            "regime": s.get("regime", "UNKNOWN"),
            "rsi_5m": s.get("rsi_5m"),
            "decision": s.get("decision", "hold"),
        })
    
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wallet": {
            "currency": settings.trading.stake_currency,
            "initial_budget": settings.trading.wallet_size,
        },
        "supervisor_controls": {
            "emergency_stop": bool(controls.get("emergency_stop", 0)),
            "max_open_trades": controls.get("max_open_trades", 3),
            "min_confidence": controls.get("min_confidence", 70),
            "ai_reasoning": controls.get("ai_reasoning", ""),
        },
        "open_trades": trades_summary,
        "open_trade_count": len(trades_summary),
        "recent_performance": {
            "winrate_pct": round(winrate, 1),
            "total_recent_trades": total,
        },
        "market_snapshots": markets,
        "agent_services": services,
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def trigger_emergency_stop(reason: str) -> str:
    """Immediately halt all new buy operations. Existing positions will still be managed by the Executor for stop-loss/take-profit. Provide a reason for audit logging."""
    repo = _get_repo()
    
    current = repo.get_supervisor_controls()
    repo.update_supervisor_controls({
        "emergency_stop": 1,
        "max_open_trades": current.get("max_open_trades", 3),
        "min_confidence": current.get("min_confidence", 70),
        "close_losers_threshold": current.get("close_losers_threshold", -5.0),
        "regime_filter_active": current.get("regime_filter_active", 1),
        "ai_reasoning": f"[MCP EMERGENCY] {reason}",
    })
    repo.add_supervisor_log(
        wallet_state="N/A",
        assessment=f"Emergency stop triggered via MCP: {reason}",
        actions="emergency_stop=1"
    )
    return json.dumps({"success": True, "action": "emergency_stop_activated", "reason": reason})


@mcp.tool()
def resume_trading(reason: str = "Manual resume via MCP") -> str:
    """Resume trading after an emergency stop. Resets emergency_stop to 0."""
    repo = _get_repo()
    
    current = repo.get_supervisor_controls()
    repo.update_supervisor_controls({
        "emergency_stop": 0,
        "max_open_trades": current.get("max_open_trades", 3),
        "min_confidence": current.get("min_confidence", 70),
        "close_losers_threshold": current.get("close_losers_threshold", -5.0),
        "regime_filter_active": current.get("regime_filter_active", 1),
        "ai_reasoning": f"[MCP RESUME] {reason}",
    })
    repo.add_supervisor_log(
        wallet_state="N/A",
        assessment=f"Trading resumed via MCP: {reason}",
        actions="emergency_stop=0"
    )
    return json.dumps({"success": True, "action": "trading_resumed", "reason": reason})


@mcp.tool()
def read_agent_memory(topic: str = "risk") -> str:
    """Read the persistent agent memory files. topic can be 'risk' for the global risk policy, or an asset name like 'BTCUSDT' for asset-specific memory."""
    mm = _get_mm()
    
    if topic.lower() == "risk":
        content = mm.read_risk_policy()
        return json.dumps({"topic": "risk_policy", "content": content})
    else:
        content = mm.read_asset_memory(topic)
        return json.dumps({"topic": f"asset_{topic}", "content": content})


@mcp.tool()
def append_agent_insight(insight: str, topic: str = "risk") -> str:
    """Append a new insight or learning to the agent's persistent memory. topic='risk' writes to the global risk policy. topic='BTCUSDT' writes to the BTC asset memory."""
    mm = _get_mm()
    
    if topic.lower() == "risk":
        mm.append_risk_insight(insight)
        return json.dumps({"success": True, "target": "risk_policy", "insight": insight})
    else:
        mm.append_asset_insight(topic, insight)
        return json.dumps({"success": True, "target": f"asset_{topic}", "insight": insight})


@mcp.tool()
def get_api_costs() -> str:
    """Get a breakdown of all AI API costs: total USD spent, tokens consumed, per-model and per-caller breakdowns."""
    from telemetry.cost_tracker import get_cost_tracker
    tracker = get_cost_tracker(str(PROJECT_ROOT))
    summary = tracker.get_summary()
    return json.dumps(summary, indent=2)


if __name__ == "__main__":
    mcp.run(transport="sse")
