import time
import json
import logging
import os
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import schedule
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Configuration setup
from config.settings import get_settings
from storage.repository import Repository
from storage.memory_manager import MemoryManager
from telemetry.cost_tracker import get_cost_tracker
from ai.nvidia_teacher import NvidiaTeacher
from storage.superbrain import get_superbrain

settings = get_settings()

# Logging setup
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
log_path = LOGS_DIR / "dream_agent.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DREAM] %(message)s",
    handlers=[logging.FileHandler(log_path, encoding='utf-8', delay=True), logging.StreamHandler()]
)
logger = logging.getLogger("dream_agent")

class DreamAgent:
    """
    Memory Consolidation Agent (Auto-Dream V11.5).
    Patterns from Claude Code (src/services/autoDream):
    1. ORIENT: State assessment.
    2. GATHER: Signal extraction (Win Rates + Feedback).
    3. CONSOLIDATE: Pattern synthesis.
    4. PRUNE & INDEX: Junk removal (Auto-Purge).
    """
    
    def __init__(self):
        self.repo = Repository()
        self.mm = MemoryManager(str(PROJECT_ROOT))
        self.tracker = get_cost_tracker(str(PROJECT_ROOT))
        
    def _get_recent_performance(self):
        """Fetches trade outcomes from the last 24 hours."""
        outcomes = self.repo.get_recent_outcomes(days=1)
        win_count = sum(1 for o in outcomes if o['was_profitable'])
        loss_count = len(outcomes) - win_count
        pnl_sum = sum(o['realized_pnl_pct'] for o in outcomes)
        return {
            "total_trades": len(outcomes),
            "wins": win_count,
            "losses": loss_count,
            "net_pnl_pct": pnl_sum
        }

    def run_dream_cycle(self):
        """
        The 4-Phase Dream Sequence (The Ultimate Jewel).
        """
        logger.info("Auto-Dream 4-Phase sequence (V11.5) initiated...")
        brain = get_superbrain()
        
        # === PHASE 1: ORIENT ===
        logger.info("[Phase 1/4] Orient — Assessing current state...")
        perf = self._get_recent_performance()
        existing_strategy = brain.get_current_strategy()
        
        # === PHASE 2: GATHER (Win Rates + Feedback) ===
        logger.info("[Phase 2/4] Gather — Extracting performance signals...")
        
        # Read feedback and outcomes
        feedback = brain.get_recent_feedback() or "No recent feedback."
        outcomes = self.repo.get_outcomes_with_details(days=3) # Look back 3 days for patterns
        
        # Calculate win rates per asset/pattern
        asset_report = ""
        low_perf_assets = []
        for asset in set(o['asset'] for o in outcomes):
            a_out = [o for o in outcomes if o['asset'] == asset]
            wins = sum(1 for o in a_out if o['was_profitable'])
            total = len(a_out)
            wr = (wins / total * 100) if total > 0 else 0
            asset_report += f"  - {asset}: {wr:.0f}% WR ({total} trades)\n"
            if total >= 2 and wr < 45: # Pattern failure threshold
                low_perf_assets.append(asset)

        # === PHASE 3: CONSOLIDATE (Synthesis) ===
        logger.info("[Phase 3/4] Consolidate — Synthesizing new Golden Rules...")
        
        # Absolute Date (Jewel from Claude Code)
        today_abs = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        prompt = f"""You are the TENGU V11.5 DREAM AGENT. Synthesis mode.
Current Date: {today_abs}
Recent PnL: {perf['net_pnl_pct']:+.2f}% ({perf['wins']}W/{perf['losses']}L)

OUTCOME ANALYSIS:
{asset_report}

RECENT FEEDBACK:
{feedback}

TASK:
1. Synthesize a TACTICAL STRATEGY for the next 2 hours.
2. Generate 3 structured GOLDEN RULES in format: [RULE] | [WHY] | [HOW].
3. Identify if any asset should be BLACKLISTED based on WR < 45%.

NEVER use relative dates like 'today' or 'tomorrow'. Use {today_abs} instead.
"""
        try:
            teacher = NvidiaTeacher() 
            new_strategy = teacher.ask(prompt)
            if new_strategy:
                brain.remember_strategy(new_strategy)
                logger.info("New Tactical Strategy consolidated in SuperBrain.")
        except Exception as e:
            logger.error(f"Consolidation failed: {e}")

        # === PHASE 4: PRUNE & INDEX (Auto-Purge) ===
        logger.info("[Phase 4/4] Prune — Cleaning junk from SuperBrain...")
        
        # 1. Prune Low Win-Rate Rules
        # If an asset has < 45% WR, find related rules and demote them
        for asset in low_perf_assets:
            logger.info(f"Auto-Purging rules for underperforming asset: {asset}")
            brain.demote_rules_for_asset(asset) # New method to mark as low priority
            
        # 2. Index Compaction (Jewel from Claude Code)
        # Keep only the freshest core rules
        brain.compact_index(max_lines=20)
        
        logger.info("Dream Cycle Complete. System optimized.")

def main():
    agent = DreamAgent()
    # Run once at bootstrap
    agent.run_dream_cycle()
    
    # Schedule every 2 hours
    schedule.every(2).hours.do(agent.run_dream_cycle)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
