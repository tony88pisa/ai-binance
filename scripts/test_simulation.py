import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone

# Fix path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import new components
from storage.repository import Repository
from storage.memory_manager import MemoryManager
from telemetry.cost_tracker import get_cost_tracker
from agents.coordinator import Coordinator
from agents.dream_agent import DreamAgent

import uuid

def sim_print(msg):
    print(f"\n[SIMULATION] === {msg} ===")

def run_simulation():
    repo = Repository()
    mm = MemoryManager(str(PROJECT_ROOT))
    tracker = get_cost_tracker(str(PROJECT_ROOT))
    coor = Coordinator()
    dreamer = DreamAgent()

    sim_print("STEP 1: Testing Cost Telemetry")
    tracker.record_call(model="dummy-sim-model", caller="sim_test", input_tokens=150, output_tokens=50, duration_ms=200, success=True)
    costs = tracker.get_summary()
    print(json.dumps(costs, indent=2))
    assert costs["total_calls"] > 0, "Cost tracker failed to record."

    sim_print("STEP 2: Testing Task State Machine (Trade Flow)")
    decision_id = f"SIM-{uuid.uuid4().hex[:6]}"
    
    # 2a. PENDING
    print("-> Opening Trade (PENDING)")
    repo.save_trade_decision({
        "id": decision_id, "asset": "SOL/USDT", "action": "BUY",
        "confidence": 85.0, "size_pct": 0.1, "thesis": "Simulated buy",
        "regime": "BULL", "status": "PENDING"
    })
    
    # 2b. CLOSING
    print("-> Updating Trade Status to CLOSING")
    repo.update_decision_status(decision_id, "CLOSING")
    
    # 2c. CLOSE with OUTCOME
    print("-> Closing Trade via Outcome")
    repo.close_trade_with_outcome({
        "id": f"OUT-{uuid.uuid4().hex[:6]}", "decision_id": decision_id,
        "realized_pnl_pct": -2.5, "was_profitable": False,
        "closed_at": datetime.now(timezone.utc).isoformat()
    })
    print("Trade flow successful.")

    sim_print("STEP 3: Testing Typed Memory")
    print("-> Injecting fake feedback from risk controller...")
    mm.save_typed_memory(
        category="feedback",
        name="sim_feedback_1",
        content="We just lost a trade on SOL/USDT because of sudden volatility. We should reduce our position sizes during chop.",
        description="Simulated Risk Event"
    )
    mm.save_typed_memory(
        category="feedback",
        name="sim_feedback_2",
        content="Another fake trade lost. Wait for BTC to stabilize before buying altcoins.",
        description="Simulated Risk Event"
    )
    
    fb = mm.get_typed_context("feedback")
    print("Accumulated Feedback:\n")
    print(fb)

    sim_print("STEP 4: Coordinator Agent Synthesis")
    print("-> Generating automated daily report (NVIDIA LLM call)...")
    health = coor.get_system_health()
    report = coor.generate_synthesis(health, costs)
    print("\n[COORDINATOR REPORT]")
    print(report)

    sim_print("STEP 5: Dream Agent Consolidation")
    print("-> Forcing the Dream Agent to synthesize a new tactical strategy from the negative feedback we just injected...")
    dreamer.run_dream_cycle()
    
    # Read the final strategy generated
    strat = mm.get_typed_context("project")
    print("\n[NEW ROLLING STRATEGY GENERATED]")
    print(strat)
    
    print("\n[SIMULATION COMPLETE] All 5 patterns executed successfully.")

if __name__ == "__main__":
    run_simulation()
