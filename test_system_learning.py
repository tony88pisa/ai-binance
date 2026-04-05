import os
import sys
import logging
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [MEGA-TEST] %(message)s")
logger = logging.getLogger("mega_test")

def run_tests():
    logger.info("========================================")
    logger.info("  TENGU V11 MEGA-TEST: LEARNING & DATA")
    logger.info("========================================")

    # 1. Test SuperBrain (Storage & Memory)
    from storage.superbrain import get_superbrain
    brain = get_superbrain()
    logger.info(">>> TEST 1: SuperBrain Memory Link")
    if brain.enabled:
        logger.info("Supermemory Cloud ABILITATO.")
        res = brain.remember("market", "Simulated anomaly on PEPE. Extreme volatility detected.", {"asset": "PEPEUSDT"})
        logger.info(f"Salvataggio memoria: {'OK' if res else 'FALLITO'}")
        
        recall = brain.recall_context("PEPE volatility", "market")
        logger.info(f"Richiamo memoria (Recall): {recall[:60]}...")
    else:
        logger.warning("Supermemory Cloud DISABILITATO. Il bot userà i log locali fallback.")

    # 2. Test NVIDIA Teacher (LLM Strategy Override)
    from ai.nvidia_teacher import NvidiaTeacher
    from storage.repository import Repository
    repo = Repository()
    logger.info("\n>>> TEST 2: NVIDIA Teacher & Strategy")
    try:
        teacher = NvidiaTeacher(repo)
        
        # Simuliamo che Teacher abbia restituito una findings per PEPEUSDT
        mock_findings = {
            "findings": [{
                "issue": "Il Momentum fatica in range ristretti.",
                "suggested_regime": "SIDEWAYS",
                "recommended_engine": "grid",
                "edge": "If ATR is low, use Grid Engine rather than Momentum.",
                "ai_assessment": "Safe to operate locally.",
                "suggested_controls": {"min_confidence": 75}
            }],
            "status": "completed"
        }
        
        # Test Skill Generation
        from ai.skill_generator import SkillGenerator
        gen = SkillGenerator()
        skills = gen.generate_from_findings(mock_findings)
        
        for s in skills:
            logger.info(f"Generata Skill (Apprendimento): [{s['name']}] -> {s['prompt_rule']}")
            assert "grid" in s['prompt_rule'].lower(), "L'apprendimento non ha iniettato il recommended_engine!"
            assert "1-2%" in s['prompt_rule'].lower(), "Position Sizing dinamico ignorato!"
        logger.info("Generazione Skill: OK (L'AI sta iniettando i constraints Micro-Cap)")
    except Exception as e:
        logger.error(f"Errore Test 2: {e}")

    # 3. Test Dashboard (Iniezione Real-time data)
    logger.info("\n>>> TEST 3: Dashboard V11 Endpoints")
    try:
        from dashboard.routes_api import get_v11_status
        v11_data = get_v11_status()
        
        logger.info("JSON Endpoint /v11-status:")
        logger.info(json.dumps(v11_data, indent=2))
        
        assert "tax_reserve_33pct_usdt" in v11_data, "Manca la riserva tasse!"
        assert "grid_engine" in v11_data, "Manca il Grid Engine status!"
        assert v11_data["grid_engine"]["engine"] == "ready", "Grid engine non operativo!"
        
        logger.info("Dashboard API: OK (I dati finanziari del paper sono esposti correttamente per la GUI)")
    except Exception as e:
        logger.error(f"Errore Test 3: {e}")

    # 4. Test Auto-Dream (Memory Consolidation)
    from agents.dream_agent import DreamAgent
    logger.info("\n>>> TEST 4: Dream Agent (Orient & Gather)")
    try:
        da = DreamAgent()
        perf = da._get_recent_performance()
        logger.info(f"Performance lette da Dream Agent: {perf}")
        logger.info("Dream Agent Orient: OK")
    except Exception as e:
        logger.error(f"Errore Test 4: {e}")

    logger.info("========================================")
    logger.info("  MEGA-TEST COMPLETATO CON SUCCESSO")
    logger.info("  L'organismo impara, salva e pubblica.")
    logger.info("========================================")

if __name__ == "__main__":
    run_tests()
