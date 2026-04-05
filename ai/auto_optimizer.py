import time
import schedule
import logging
from datetime import datetime
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging dedicato
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [OPTIMIZER] %(message)s",
                    handlers=[logging.FileHandler(LOG_DIR / "brute_force.log"), logging.StreamHandler()])
logger = logging.getLogger("auto_optimizer")

from storage.repository import Repository
from ai.skill_validator import SkillValidator
from storage.superbrain import SuperBrain

def optimize_all_markets():
    logger.info("Avvio Super-Ciclo di Ottimizzazione Brute Force...")
    repo = Repository()
    validator = SkillValidator(repo)
    brain = SuperBrain()
    
    # Gli asset speculativi da dominare
    try:
        from agents.squad_crypto import CRYPTO_SYMBOLS
        assets = CRYPTO_SYMBOLS
    except ImportError:
        assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    
    for asset in assets:
        logger.info(f"Ottimizzazione param geometrici per {asset}...")
        
        # Skill template che verrà passata al Validator e iniettata di varianti
        skill_template = {
            "name": f"BruteForce_{asset}_Alpha",
            "target_asset": asset
        }
        
        result = validator.validate(skill_template)
        
        if result["passed"]:
            logger.info(f"[{asset}] Trovato Edge Momentum! Sortino: {result.get('sortino', 'N/A')} | WR: {result['win_rate']}% | Kelly: {result.get('kelly_size', 'N/A')}%")
            logger.info(f"Regola Base: {result['prompt_rule']}")
            
            mem_content = f"STATISTICAL FACT [{asset}]: {result['prompt_rule']}. Tested trades: {result['trade_count']}. PnL Edge: {result['avg_pnl']}. Strictly follow these math thresholds to maximize profit."
            
            try:
                brain.remember("strategies", mem_content, {"asset": asset, "type": "statistical_fact"})
                logger.info(f"[{asset}] Strategia pushata nel SuperBrain con successo.")
            except Exception as e:
                logger.error(f"Errore push SuperBrain: {e}")
                
            candidate = {
                "skill_id": f"BF-{asset}",
                "name": skill_template["name"],
                "version": "2.0.0",
                "validation_status": "API-VALIDATED",
                "skill_json": result["optimized_params"],
                "created_at": datetime.now().isoformat()
            }
            repo.save_skill_candidate(candidate)
            repo.save_skill_validation(f"BF-{asset}", result)
        else:
            logger.warning(f"[{asset}] Nessun vantaggio Momentum trovato. Valutiamo Grid Trading...")
        
        # --- GRID TRADING EVALUATION (via CCXT) ---
        try:
            from ai.grid_engine import AdaptiveGridEngine, GridConfig
            import ccxt
            import numpy as np
            from config.settings import get_settings
            
            _s = get_settings()
            _ex_cls = getattr(ccxt, _s.exchange.name.lower(), ccxt.binance)
            _ex = _ex_cls({"enableRateLimit": True})
            ccxt_symbol = asset if "/" in asset else asset.replace("USDT", "/USDT")
            ohlcv = _ex.fetch_ohlcv(ccxt_symbol, "5m", limit=500)
            closes = np.array([float(k[4]) for k in ohlcv])
            highs = np.array([float(k[2]) for k in ohlcv])
            lows = np.array([float(k[3]) for k in ohlcv])
            
            # ATR semplice
            trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(1, len(closes))]
            atr = float(np.mean(trs[-14:])) if len(trs) >= 14 else float(np.std(closes))
            
            grid_cfg = GridConfig(symbol=asset.replace("USDT", "/USDT"), total_budget_usdt=50.0, grid_levels=5)
            grid_engine = AdaptiveGridEngine(grid_cfg)
            grid_perf = grid_engine.simulate_grid_performance(closes, atr)
            
            if grid_perf["viable"]:
                logger.info(f"[{asset}] 📊 Grid Trading viabile! Fills={grid_perf['total_fills']}, PnL={grid_perf['realized_pnl_usdt']}$, Stima mensile={grid_perf['monthly_estimate_usdt']}$/mese")
                grid_mem = f"GRID STRATEGY [{asset}]: Grid trading è viabile. Fills stimati: {grid_perf['total_fills']}. PnL simulato: {grid_perf['realized_pnl_usdt']}$. In mercato laterale, privilegiare Grid su Momentum."
                try:
                    brain.remember("strategies", grid_mem, {"asset": asset, "type": "grid_assessment"})
                except Exception as e:
                    logger.error(f"Errore push Grid assessment: {e}")
            else:
                logger.info(f"[{asset}] Grid non viabile: {grid_perf['reason']}")
        except Exception as e:
            logger.warning(f"[{asset}] Grid evaluation fallita: {e}")

if __name__ == "__main__":
    logger.info("BRUTE FORCE OPTIMIZER Daemon avviato. Esecuzione ogni 6 ore.")
    
    # Prima esecuzione immediata all'avvio
    optimize_all_markets()
    
    # Schedulazione
    schedule.every(6).hours.do(optimize_all_markets)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
