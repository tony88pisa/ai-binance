import time
import json
import logging
import uuid
import schedule
from datetime import datetime, timezone
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SQUAD_EQUITY] %(message)s",
                    handlers=[logging.FileHandler(LOGS_DIR / "squad_equity.log", encoding='utf-8', delay=True), logging.StreamHandler()])
logger = logging.getLogger("squad_equity")

from config.settings import get_settings
from storage.repository import Repository
import ai.types as ai_types
import ai.decision_engine as decision_engine
from services.exchange_executor import ExchangeExecutor
class MockEquityBroker:
    def __init__(self):
        self.wallet = 10000.0
    def get_balance(self): return self.wallet
    def open_position(self, asset, price, size): return True
from services.equity_provider import EquityProvider

try:
    from supermemory import Supermemory
    sm_client = Supermemory(api_key=os.getenv("SUPERMEMORY_API_KEY"))
except Exception as e:
    sm_client = None

settings = get_settings()

def job_ai_analysis(repo, executor):
    try:
        controls = repo.get_supervisor_controls()
        if controls.get("emergency_stop", 0):
            logger.warning("EMERGENCY_STOP ACTIVE. Skipping AI analysis.")
            return

        CURRENCY = settings.trading.stake_currency
        wallet_current = executor.get_balance(CURRENCY)
        max_trades = controls.get("max_open_trades", settings.risk.max_open_trades)
        min_conf = controls.get("min_confidence", settings.risk.min_confidence_buy)

        open_trades = repo.get_open_decisions()
        if len(open_trades) >= max_trades:
            logger.info("Portfolio full. Skipping buy analysis.")
            return

        snapshots = repo.get_latest_snapshots()
        # [SQUAD EQUITY] Solo asset Tradizionali ammessi!
        ep = EquityProvider()
        equity_assets = ep.get_market_list("ALL")
        
        for snap in snapshots:
            asset = snap["asset"]
            if any(t["asset"] == asset for t in open_trades):
                continue
                
            if asset not in equity_assets:
                continue
                
            intel_types = ai_types.MarketIntelligence(
                asset=asset, close_price=snap["price"] or 0.0, 
                rsi_5m=snap.get("rsi_5m") or 50.0, 
                rsi_1h=snap.get("rsi_1h") or 50.0, 
                macd_5m=snap.get("macd_5m") or 0.0, 
                macd_1h=snap.get("macd_1h") or 0.0, 
                market_regime=snap.get("regime") or "UNKNOWN",
                news_count=3, research_staleness_seconds=10.0
            )
            
            ai_decision = decision_engine.evaluate(intel_types, repo)
            
            # [LIVING_BOT] Save analysis snapshot for Arena Live
            repo.upsert_market_snapshot({
                "asset": asset, "price": snap["price"], 
                "rsi_5m": snap.get("rsi_5m"), "rsi_1h": snap.get("rsi_1h"),
                "macd_5m": snap.get("macd_5m"), "macd_1h": snap.get("macd_1h"),
                "atr_5m": snap.get("atr_5m"), "decision": ai_decision.decision.value,
                "confidence": ai_decision.confidence, "regime": snap.get("regime", "UNKNOWN"),
                "consensus_score": ai_decision.confidence / 100.0, "position_size_pct": 0.0,
                "atr_stop_distance": 0.0, "why_not_trade": ai_decision.thesis
            })
            
            # [LIVING_BOT] Human-readable log
            logger.info(f"Thinking about {asset}: {ai_decision.thesis} (Conf: {ai_decision.confidence}%)")
            
            # Determiniamo l'identità dell'agente logico
            agent_identity = "Alpha-Quantum"
            if ai_decision.confidence < 75:
                agent_identity = "Trend-Scout"
                
            if ai_decision.decision.value == "buy" and ai_decision.confidence >= min_conf:
                if snap.get("regime") not in ["TREND_DOWN", "HIGH_VOL_CHAOS"]:
                    # --- HUMAN VERIFICATION GATE ---
                    if getattr(ai_decision, 'requires_human_verification', False):
                        logger.warning(f"🚦 HUMAN VERIFICATION REQUIRED per {asset}. Trade in coda.")
                        repo.log_activity("squad_equity", "HUMAN_GATE", f"{asset}: requires manual approval")
                        continue
                    
                    # Dynamic Kelly Sizing (stesso della squad_crypto)
                    dynamic_size = controls.get("position_size_usdt", None)
                    ep = EquityProvider()
                    equity_assets = ep.get_market_list("ALL")
                    
                    if asset in equity_assets:
                        equity_broker = MockEquityBroker()
                        wallet_eq = equity_broker.get_balance()
                        
                        if dynamic_size and dynamic_size > 0:
                            pos_value = min(dynamic_size, wallet_eq * 0.30)
                        else:
                            pos_value = wallet_eq * 0.02  # Regola 1-2%
                        
                        if pos_value < 5.0:
                            pos_value = min(5.0, wallet_eq * 0.50)
                        
                        logger.info(f"[EQUITY_SQUAD] PLACING BUY: {asset} for ${pos_value:.2f} (Kelly/Dynamic)")
                        size_pct = pos_value / wallet_eq if wallet_eq > 0 else 0.10
                        
                        success = equity_broker.open_position(asset, snap["price"], pos_value)
                        target_ex_id = f"EQ-{uuid.uuid4().hex[:8]}" if success else None
                        
                        if success:
                            repo.save_trade_decision({
                                "id": f"DEC-EQUITY-{uuid.uuid4().hex[:8]}", "asset": asset, "action": "buy",
                                "confidence": ai_decision.confidence, "size_pct": size_pct, 
                                "thesis": ai_decision.thesis, "regime": snap.get("regime", "UNKNOWN"), 
                                "entry_price": snap["price"], "atr_stop_distance": snap.get("atr_5m", 0.0) * 1.5,
                                "status": "OPEN", "inner_monologue": ai_decision.inner_monologue, 
                                "agent_name": "WallStreet-Agent", "exchange_order_id": target_ex_id
                            })
                            
                            # --- Supermemory Logging ---
                            if sm_client:
                                try:
                                    memory_blob = {
                                        "asset": asset, "action": "BUY_EQUITY", "price": snap["price"],
                                        "confidence": ai_decision.confidence, "thesis": ai_decision.thesis,
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                                    sm_client.add(content=json.dumps(memory_blob))
                                    logger.info(f"✅ Equity Thesis logged to Supermemory for {asset}")
                                except Exception as sme:
                                    logger.error(f"Supermemory log failed: {sme}")
                            
        repo.update_service_heartbeat("squad_equity", json.dumps({
            "mode": "ACTIVE", "last_run": datetime.now(timezone.utc).isoformat()
        }))
        logger.info(f"AI Analysis complete. Open trades: {len(open_trades)}")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("Starting Market Analyzer Agent...")
    repo = Repository()
    executor = ExchangeExecutor()
    
    schedule.every(5).minutes.do(job_ai_analysis, repo, executor)
    job_ai_analysis(repo, executor)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
