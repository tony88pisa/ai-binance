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
    
    # Gli asset principali da dominare
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
            logger.info(f"[{asset}] Trovato Edge Vincente! WR: {result['win_rate']}% | PnL: {result['avg_pnl']}% | DD: {result['max_drawdown']}")
            logger.info(f"Regola Base: {result['prompt_rule']}")
            
            # Pubblichiamo la memoria nel SuperBrain affinché l'intero Swarm la utilizzi (Dreamer + DecisionEngine)
            mem_content = f"STATISTICAL FACT [{asset}]: {result['prompt_rule']}. Tested trades: {result['trade_count']}. PnL Edge: {result['avg_pnl']}. Strictly follow these math thresholds to maximize profit."
            
            try:
                brain.remember("strategies", mem_content, {"asset": asset, "type": "statistical_fact"})
                logger.info(f"[{asset}] Strategia pushata nel SuperBrain con successo.")
            except Exception as e:
                logger.error(f"Errore push SuperBrain: {e}")
                
            # Salviamo su DB SQL per visualizzazione
            candidate = {
                "skill_id": f"BF-{asset}",
                "name": skill_template["name"],
                "version": "1.0.0",
                "validation_status": "API-VALIDATED",
                "skill_json": result["optimized_params"],
                "created_at": datetime.now().isoformat()
            }
            repo.save_skill_candidate(candidate)
            repo.save_skill_validation(f"BF-{asset}", result)
        else:
            logger.warning(f"[{asset}] Nessun vantaggio matematico trovato con DD < 10%. Verrà usato il fallback standard.")

if __name__ == "__main__":
    logger.info("BRUTE FORCE OPTIMIZER Daemon avviato. Esecuzione ogni 6 ore.")
    
    # Prima esecuzione immediata all'avvio
    optimize_all_markets()
    
    # Schedulazione
    schedule.every(6).hours.do(optimize_all_markets)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
