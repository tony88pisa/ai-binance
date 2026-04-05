import time
import json
import logging
import os
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import schedule

# Configuration setup
from config.settings import get_settings
from storage.repository import Repository
from storage.memory_manager import MemoryManager
from telemetry.cost_tracker import get_cost_tracker

settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

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
    Memory Consolidation Agent (Auto-Dream).
    Wakes up every 2 hours to synthesize recent trades and feedback 
    into a fresh rolling tactical strategy.
    """
    
    def __init__(self):
        self.repo = Repository()
        self.mm = MemoryManager(str(PROJECT_ROOT))
        self.tracker = get_cost_tracker(str(PROJECT_ROOT))
        
    def _get_recent_performance(self):
        """Fetches trade outcomes from the last 24 hours to give sense of momentum."""
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
        
    def prune_old_feedback(self):
        """Removes feedback files older than 24 hours to prevent context window bloat."""
        feedback_dir = self.mm.categories["feedback"]
        pruned = 0
        for file in feedback_dir.glob("*.md"):
            try:
                mtime = datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc)
                if (datetime.now(timezone.utc) - mtime) > timedelta(hours=24):
                    file.unlink()
                    pruned += 1
            except Exception as e:
                logger.error(f"Failed to prune {file}: {e}")
        if pruned > 0:
            logger.info(f"Pruned {pruned} old feedback files.")

    def run_dream_cycle(self):
        """
        1. Orients: Reads recent stats.
        2. Gathers: Reads accumulated feedback.
        3. Consolidates: Asks NVIDIA NIM to synthesize a tactical strategy.
        4. Prunes: Cleans old feedback.
        """
        logger.info("Auto-Dream sequence initiated. Analyzing recent market phase...")
        
        # 1 & 2: Orient & Gather
        perf = self._get_recent_performance()
        feedback = self.mm.get_typed_context("feedback")
        
        if not feedback or "Nessun dato" in feedback:
            logger.info("No significant new feedback to consolidate. Generating baseline rolling strategy.")
            feedback = "No specific errors or anomalies detected recently. Typical market flow."
            
        # 3. Consolidate via LLM
        api_key = os.getenv("NVIDIA_API_KEY")
        model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        
        prompt = f"""
        You are the 'Auto-Dream' consolidation layer for an autonomous crypto trading bot.
        You wake up every 2 hours to process recent memories and synthesize a tactical strategy.
        
        PAST 24H PERFORMANCE:
        - Trades: {perf['total_trades']}
        - Wins/Losses: {perf['wins']}/{perf['losses']}
        - Net PnL: {perf['net_pnl_pct']:.2f}%
        
        RECENT RAW FEEDBACK (from Risk Controller and System logs):
        {feedback}
        
        TASK:
        Write a concise, 3-to-4 bullet point "Tactical Strategy" for the next 2 hours.
        Resolve any contradictions in the raw feedback. Focus on what the Analyzer agent should look for right now (e.g., "avoid breakouts due to chop", "increase confidence threshold", "favor small pullbacks on SOL").
        
        Do NOT write code. Output only the plain Markdown bullet points.
        """
        
        try:
            t_start = time.time()
            res = requests.post(url, json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 300
            }, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)
            res.raise_for_status()
            duration_ms = int((time.time() - t_start) * 1000)
            
            resp_data = res.json()
            strategy_content = resp_data['choices'][0]['message']['content'].strip()
            
            # Track cost
            try:
                usage = resp_data.get("usage", {})
                self.tracker.record_call(
                    model=model, caller="dream_agent",
                    input_tokens=usage.get("prompt_tokens", 0),
                    output_tokens=usage.get("completion_tokens", 0),
                    duration_ms=duration_ms, success=True
                )
            except Exception:
                pass
            
            # Save the new tactical strategy
            self.mm.save_typed_memory(
                category="project",
                name="current_strategy",
                content=strategy_content,
                description="Rolling 2-hour tactical strategy generated by Dream Agent."
            )
            logger.info("Successfully consolidated memory into new 'current_strategy'.")
            
        except Exception as e:
            logger.error(f"Dream LLM synthesis failed: {e}")
            
        # 4. Prune
        self.prune_old_feedback()
        
        # Heartbeat
        self.repo.update_service_heartbeat("dream_agent", json.dumps({
            "status": "sleeping",
            "last_dream": datetime.now(timezone.utc).isoformat()
        }))

if __name__ == "__main__":
    import sys
    da = DreamAgent()
    
    # Allow running once manually via CLI flag
    if "--force" in sys.argv:
        logger.info("Forcing Dream Cycle via CLI...")
        da.run_dream_cycle()
        sys.exit(0)
        
    logger.info("Dream Agent active. Scheduled to run every 2 hours.")
    
    # Schedule every 2 hours
    schedule.every(2).hours.do(da.run_dream_cycle)
    
    # Run once on startup
    da.run_dream_cycle()
    
    while True:
        schedule.run_pending()
        time.sleep(60) # Sleep longer since it's a slow job
