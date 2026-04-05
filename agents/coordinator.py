import time
import json
import logging
import os
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Configuration setup
from config.settings import get_settings
from storage.repository import Repository
from storage.memory_manager import MemoryManager
from telemetry.cost_tracker import get_cost_tracker
from modules.notifications_hub import NotificationsHub

settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Logging setup
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
log_path = LOGS_DIR / "coordinator.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [COORDINATOR] %(message)s",
    handlers=[logging.FileHandler(log_path, encoding='utf-8', delay=True), logging.StreamHandler()]
)
logger = logging.getLogger("coordinator")

class Coordinator:
    """
    Top-level Orchestrator Agent. 
    Synthesizes global state, manages global risk, and generates daily reports.
    Inspired by coordinatorMode.ts.
    """
    
    def __init__(self):
        self.repo = Repository()
        self.mm = MemoryManager(str(PROJECT_ROOT))
        self.tracker = get_cost_tracker(str(PROJECT_ROOT))
        self.daily_budget_limit = float(os.getenv("AI_DAILY_BUDGET", "2.00"))
        self.notifier = NotificationsHub()

    def get_system_health(self) -> dict:
        """Checks if all agents are active via heartbeats."""
        agents = ["squad_crypto", "squad_equity", "news_trader", "dream_agent"]
        health = {}
        for agent in agents:
            state = self.repo.get_service_state(agent)
            hb_str = state.get("last_heartbeat")
            if hb_str:
                hb_time = datetime.fromisoformat(hb_str)
                is_active = (datetime.now(timezone.utc) - hb_time) < timedelta(minutes=15)
                health[agent] = "OK" if is_active else "STALE"
            else:
                health[agent] = "MISSING"
        return health

    def check_circuit_breakers(self, health: dict, costs: dict):
        """Emergency stop if costs or health are critical."""
        reasons = []
        
        # 1. Cost check
        total_cost = costs.get("total_cost_usd", 0.0)
        if total_cost > self.daily_budget_limit:
            reasons.append(f"Daily AI budget exceeded (${total_cost:.2f} > ${self.daily_budget_limit:.2f})")
            
        # 2. Health check
        stale_count = sum(1 for v in health.values() if v != "OK")
        if stale_count >= 2:
            reasons.append(f"Multiple agents are inactive ({stale_count} failures detected)")

        if reasons:
            logger.warning(f"CIRCUIT BREAKER TRIGGERED: {'; '.join(reasons)}")
            controls = self.repo.get_supervisor_controls()
            if not controls.get("emergency_stop"):
                self.repo.update_supervisor_controls({
                    **controls,
                    "emergency_stop": 1,
                    "ai_reasoning": f"COORDINATOR: Global Circuit Breaker triggered. Reasons: {reasons}"
                })
                logger.info("Emergency Stop activated globally.")
                self.notifier.broadcast(f"CIRCUIT BREAKER TRIGGERED: {'; '.join(reasons)}", level="ERROR")
        else:
            # Auto-resume if only 1 agent was stale and now is OK? (Maybe not, keep it manual for safety)
            pass

    def generate_synthesis(self, health: dict, costs: dict) -> str:
        """Uses LLM to synthesize a daily project report."""
        api_key = os.getenv("NVIDIA_API_KEY")
        model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        
        # Gather data for prompt
        open_trades = self.repo.get_open_decisions()
        history = self.repo.get_history(limit=5)
        
        prompt = f"""
        You are the Global Coordinator for a Multi-Agent AI Trading Bot.
        Mission: Synthesize a human-readable Performance & Health report.
        
        SYSTEM STATE:
        - Agent Health: {json.dumps(health, indent=2)}
        - API Costs (Today): ${costs.get('total_cost_usd', 0.0):.4f}
        - Current Open Trades: {len(open_trades)}
        - Recent Closed Trades: {len(history)}
        
        Task: 
        1. Evaluate if the bot is healthy.
        2. Identify if we are close to the ${self.daily_budget_limit} budget limit.
        3. Summarize recent trade outcomes.
        4. Write a 2-paragraph professional report.
        
        Format as Markdown. Include a 'Verdict' (GREEN/YELLOW/RED).
        """
        
        try:
            res = requests.post(url, json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
            res.raise_for_status()
            return res.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"Failed to generate report: {e}"

    def run_cycle(self):
        """Main coordination loop."""
        try:
            logger.info("Coordinator cycle starting...")
            health = self.get_system_health()
            costs = self.tracker.get_summary()
            
            # 1. Safety Checks
            self.check_circuit_breakers(health, costs)
            
            # 2. Daily Report (Every 24h or manual trigger)
            # Simplified: generate one whenever this runs for now, or check file age
            report_path = PROJECT_ROOT / "ai_memory" / "project" / "daily_synthesis.md"
            should_report = True
            if report_path.exists():
                mtime = datetime.fromtimestamp(report_path.stat().st_mtime, tz=timezone.utc)
                if (datetime.now(timezone.utc) - mtime) < timedelta(hours=4):
                    should_report = False
            
            if should_report:
                logger.info("Generating synthesized report...")
                report_content = self.generate_synthesis(health, costs)
                self.mm.save_typed_memory(
                    category="project",
                    name="Daily Synthesis",
                    content=report_content,
                    description="Synthetic oversight report generated by the Coordinator Agent."
                )
                self.notifier.broadcast(f"Daily Synthesis Report:\n{report_content[:1500]}")
                with open(report_path, "w", encoding='utf-8') as f:
                    f.write(report_content)
                logger.info("Report saved to ai_memory/project/daily_synthesis.md")

            # 3. Heartbeat
            self.repo.update_service_heartbeat("coordinator", json.dumps({
                "status": "watching",
                "health_check": health,
                "cost_check": costs.get("total_cost_usd", 0.0)
            }))
            
            logger.info("Coordinator cycle complete.")
        except Exception as e:
            logger.error(f"Coordinator error: {e}", exc_info=True)

if __name__ == "__main__":
    c = Coordinator()
    # For a persistent agent, use a loop. For a task-based one, run once then schedule.
    # We'll use a loop like the others for consistency.
    logger.info("Coordinator Agent active.")
    while True:
        c.run_cycle()
        time.sleep(300) # Every 5 minutes
