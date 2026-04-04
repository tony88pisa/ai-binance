import sys
import os
import time
import json
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import Repository
from storage.memory_manager import MemoryManager
from agents.dream_agent import DreamAgent
from telemetry.cost_tracker import get_cost_tracker
import uuid

def sim_print(msg):
    print(f"\n[STRESS TEST] >>> {msg}")

def run_stress_test():
    repo = Repository()
    mm = MemoryManager(str(PROJECT_ROOT))
    tracker = get_cost_tracker(str(PROJECT_ROOT))
    dreamer = DreamAgent()
    
    sim_print("INIZIO STRESS TEST AD ALTA FREQUENZA (Simulazione 20 Minuti Accelerati)")
    
    # Generiamo 60 "tick" di mercato ad altissima volatilità, rappresentando 20 minuti reali veloci.
    # Evitiamo 1200 tick per non bruciare la CPU con Ollama, 60 bastano per lo stress test logico.
    
    base_price = 65000.0
    trades_executed = 0
    start_time = time.time()
    
    for i in range(1, 31): # 30 tick = 30 chiamate logiche
        # Simulazione crollo flash o pump
        volatility = random.uniform(-0.05, 0.05) # +/- 5% in secondi
        current_price = base_price * (1 + volatility)
        regime = "BEAR_CRASH" if volatility < -0.02 else "BULL_PUMP" if volatility > 0.02 else "CHOPPING"
        
        # Scriviamo il dato nel DB in modo frenetico
        repo.upsert_market_snapshot({
            "asset": "BTC/USDT", "price": current_price, "rsi_5m": random.uniform(10, 90),
            "rsi_1h": 50, "macd_5m": random.uniform(-100, 100), "macd_1h": 0, "atr_5m": 500,
            "decision": "WAIT", "confidence": 0, "regime": regime, "consensus_score": 0,
            "position_size_pct": 0.1, "atr_stop_distance": 0.02, "why_not_trade": ""
        })
        
        # Simuliamo che in questi chop il risk controller immetta feedback contrastanti
        if regime == "BEAR_CRASH":
            sys.stdout.write(f"\rTick {i}/30 - CRASH! Price: {current_price:.2f} | ")
            mm.save_typed_memory("feedback", f"stress_bear_{i}", f"Sudden crash to {current_price}. Stop buying.", "Simulated Bear")
            
            # Simulate a panic sell
            decision_id = f"STRESS-{uuid.uuid4().hex[:6]}"
            repo.save_trade_decision({
                "id": decision_id, "asset": "BTC/USDT", "action": "SELL",
                "confidence": 99.0, "size_pct": 0.5, "thesis": "Panic sell on crash",
                "regime": regime, "status": "PENDING"
            })
            repo.update_decision_status(decision_id, "CLOSING")
            repo.close_trade_with_outcome({
                "id": f"OUT-{uuid.uuid4().hex[:6]}", "decision_id": decision_id,
                "realized_pnl_pct": -5.0, "was_profitable": False,
                "closed_at": datetime.now(timezone.utc).isoformat()
            })
            trades_executed += 1
            
        elif regime == "BULL_PUMP":
            sys.stdout.write(f"\rTick {i}/30 - PUMP!  Price: {current_price:.2f} | ")
            mm.save_typed_memory("feedback", f"stress_bull_{i}", f"Fast pump to {current_price}. FOMO buy active.", "Simulated Bull")
            
            # Simulate fomo buy
            decision_id = f"STRESS-{uuid.uuid4().hex[:6]}"
            repo.save_trade_decision({
                "id": decision_id, "asset": "BTC/USDT", "action": "BUY",
                "confidence": 90.0, "size_pct": 0.2, "thesis": "FOMO on pump",
                "regime": regime, "status": "PENDING"
            })
            repo.update_decision_status(decision_id, "CLOSING")
            repo.close_trade_with_outcome({
                "id": f"OUT-{uuid.uuid4().hex[:6]}", "decision_id": decision_id,
                "realized_pnl_pct": 2.0, "was_profitable": True,
                "closed_at": datetime.now(timezone.utc).isoformat()
            })
            trades_executed += 1
        else:
            sys.stdout.write(f"\rTick {i}/30 - CHOP   Price: {current_price:.2f} | ")
            time.sleep(0.1) # Simulate minor delay
            
        sys.stdout.flush()
        
    duration = time.time() - start_time
    sim_print(f"STRESS TEST MARKET TICK COMPLETATO IN {duration:.2f} SECONDI")
    sim_print(f"Trade eseguiti dalla State Machine sotto stress: {trades_executed}")
    
    sim_print("VERIFICA MEMORIA (Il sistema è stato inondato di feedback contrastanti PUMP/CRASH)")
    fb_files = list(mm.categories["feedback"].glob("*.md"))
    print(f"File di feedback in memoria: {len(fb_files)}")
    
    sim_print("ESECUZIONE DREAM AGENT CON NEMOTRON 120B")
    print("Tentativo di consolidare il panico di mercato in una strategia logica. Attendi circa 40-60 sec...")
    try:
        dreamer.run_dream_cycle()
        strat = mm.get_typed_context("project")
        print("\n=== NUOVA STRATEGIA SINTETIZZATA DAL SOGNATORE (NEMOTRON 120B) ===")
        print(strat)
    except Exception as e:
        print(f"Errore durante l'esecuzione del sognatore: {e}")

if __name__ == "__main__":
    run_stress_test()
