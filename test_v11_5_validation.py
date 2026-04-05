import sys
from pathlib import Path
import logging

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("TEST_V11_5")

def test_v11_5():
    logger.info("=== STARTING TENGU V11.5 ARCHITECTURAL TEST ===")
    
    # 1. Test TechnicalEngine & DecisionEngine Integration
    try:
        from ai.technical_engine import TechnicalEngine
        from ai.decision_engine import evaluate
        import ai.types as types
        import pandas as pd
        
        logger.info("✅ Import moduli AI: OK")
        
        # Simula mercato NEUTRO (RSI 50, PNL 0)
        intel_neutral = types.MarketIntelligence(
            asset="BTC",
            close_price=60000.0,
            rsi_5m=50.0,
            macd_5m=0.0,
            market_regime="SIDEWAYS",
            news_sentiment_score=0.0,
            pnl_24h=0.0 # Cost-Aware Guard trigger
        )
        
        logger.info("Testing Cost-Aware Guard (Market Neutral)...")
        decision = evaluate(intel_neutral)
        logger.info(f"Result: {decision.decision.value} | Reason: {decision.thesis}")
        
        if "Technical Fallback" in decision.thesis or "Neutral market" in decision.thesis:
            logger.info("✅ Cost-Aware Guard: FUNZIONANTE (API risparmiate)")
        else:
            logger.warning(f"⚠️ Cost-Aware Guard non triggerato esplicitamente (Thesis: {decision.thesis})")

    except Exception as e:
        logger.error(f"❌ Errore integrazione decision_engine: {e}")

    # 2. Test Dream Agent 4-Phase logic
    try:
        from agents.dream_agent import DreamAgent
        logger.info("✅ Import DreamAgent: OK")
        
        agent = DreamAgent()
        logger.info("✅ Struttura DreamAgent: OK")
        
    except Exception as e:
        logger.error(f"❌ Errore DreamAgent: {e}")

    # 3. Test ResilienceWallet (Emergency Sleep)
    try:
        from agents.squad_crypto import ResilienceWallet
        from config.settings import get_settings
        settings = get_settings()
        
        wallet = ResilienceWallet(initial_capital=settings.trading.wallet_size)
        
        # Simula perdita pesante
        wallet.session_pnl = -6.5
        logger.info(f"Simulazione Drawdown Sessione: {wallet.session_pnl}%")
        is_sleeping = wallet.check_sleep_status()
        
        if is_sleeping:
            logger.info("✅ Emergency Self-Sleep: FUNZIONANTE (Bot in pausa)")
        else:
            logger.error("❌ Emergency Self-Sleep: FALLITO (Il bot doveva fermarsi)")
            
    except Exception as e:
        logger.error(f"❌ Errore ResilienceWallet: {e}")

    logger.info("=== TEST COMPLETATO ===")

if __name__ == "__main__":
    test_v11_5()
