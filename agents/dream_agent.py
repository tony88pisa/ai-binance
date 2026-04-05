import time
import json
import logging
import os
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import schedule
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Configuration setup
from config.settings import get_settings
from storage.repository import Repository
from storage.memory_manager import MemoryManager
from telemetry.cost_tracker import get_cost_tracker
from ai.skill_generator import SkillGenerator
from ai.skill_validator import SkillValidator
from ai.promotion_gate import PromotionGate
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
        logger.info("Auto-Dream 4-Phase sequence initiated...")
        brain = get_superbrain()
        
        # === PHASE 1: ORIENT ===
        logger.info("[Phase 1/4] Orient — Reading current state...")
        perf = self._get_recent_performance()
        
        # Read existing strategy from SuperBrain
        existing_strategy = brain.get_current_strategy()
        if existing_strategy:
            logger.info(f"Current strategy found ({len(existing_strategy)} chars). Will update, not duplicate.")
        
        # === PHASE 2: GATHER ===
        logger.info("[Phase 2/4] Gather — Collecting recent signal...")
        
        # Read feedback from SuperBrain first, fallback to local files
        feedback = brain.get_recent_feedback()
        if not feedback:
            feedback = self.mm.get_typed_context("feedback")
        
        if not feedback or "Nessun dato" in feedback:
            feedback = "No specific errors or anomalies detected recently. Typical market flow."
        
        # Get market context from SuperBrain
        market_ctx = brain.recall_context(
            "recent trading signals, news sentiment, and market patterns",
            "market", limit=5
        )
            
        # === PHASE 3: CONSOLIDATE via LLM ===
        logger.info("[Phase 3/4] Consolidate — Synthesizing tactical strategy via LLM...")
        api_key = os.getenv("NVIDIA_API_KEY")
        model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        
        prompt = f"""# Dream: Memory Consolidation & Tactical Strategy

You are the 'Auto-Dream' consolidation layer for the Tengu V10 autonomous trading swarm.
You wake up every 30 minutes to consolidate recent memories and generate a tactical strategy.

## Phase 1 — Current State

PAST 24H PERFORMANCE:
- Total Trades: {perf['total_trades']}
- Wins/Losses: {perf['wins']}/{perf['losses']}
- Net PnL: {perf['net_pnl_pct']:.2f}%

EXISTING STRATEGY (to update, not duplicate):
{existing_strategy[:300] if existing_strategy else 'No previous strategy.'}

## Phase 2 — Recent Signal

FEEDBACK FROM RISK CONTROLLER AND AGENTS:
{feedback[:800]}

MARKET CONTEXT (news, signals):
{market_ctx[:500] if market_ctx else 'No recent market signals.'}

## Phase 3 — Consolidate

Do the following:
1. Identify contradictions between the existing strategy and new data. Resolve them.
2. Convert any relative dates to absolute dates.
3. If the previous strategy worked (positive PnL), refine it. If it failed, change approach.
4. Focus on concrete, actionable rules (e.g., "avoid BTC breakouts due to chop", "increase min confidence to 80%").

## Phase 4 — Output

Write a concise 4-to-6 bullet point "Tactical Strategy" for the NEXT 30 MINUTES.
Be aggressive in adapting to rapidly changing conditions.
Each bullet must be specific and actionable — no vague advice like "be careful".

Do NOT write code. Output only the plain Markdown bullet points."""
        
        try:
            t_start = time.time()
            res = requests.post(url, json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 400
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
            
            # Save to SuperBrain (primary)
            brain.remember_strategy(strategy_content)
            
            # Save to local files (fallback)
            self.mm.save_typed_memory(
                category="project",
                name="current_strategy",
                content=strategy_content,
                description="Rolling 30-min tactical strategy generated by Dream Agent V2."
            )
            logger.info(f"[Phase 3/4] Strategy consolidated ({len(strategy_content)} chars, {duration_ms}ms).")
            
        except Exception as e:
            logger.error(f"Dream LLM synthesis failed: {e}")
            
        # 4. Skill Generation (Auto-Evolve)
        try:
            logger.info("Running Skill Generation pipeline...")
            teacher = NvidiaTeacher(self.repo)
            analysis = teacher.analyze()
            if analysis.get("findings"):
                gen = SkillGenerator()
                candidates = gen.generate_from_findings(analysis)
                validator = SkillValidator(self.repo)
                gate = PromotionGate(self.repo)
                for skill in candidates:
                    val_result = validator.validate(skill)
                    if gate.evaluate(skill["skill_id"], val_result):
                        self.repo.save_skill_candidate(skill, status="approved")
                        logger.info(f"✅ New Skill promoted: {skill['name']} (edge: {skill['expected_edge'][:60]})")
                    else:
                        self.repo.save_skill_candidate(skill, status="candidate")
                        logger.info(f"📋 Skill candidate saved: {skill['name']} (reason: {val_result.get('reason', 'N/A')})")
                logger.info(f"Skill pipeline complete: {len(candidates)} candidates processed.")
            else:
                logger.info("No findings from NVIDIA Teacher. Skill generation skipped.")
        except Exception as e:
            logger.error(f"Skill generation failed (non-critical): {e}")
        
        # 5. Prune old feedback
        self.prune_old_feedback()
        
        # 6. Heartbeat
        self.repo.update_service_heartbeat("dream_agent", json.dumps({
            "status": "sleeping",
            "last_dream": datetime.now(timezone.utc).isoformat(),
            "cycle_interval": "30min"
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
    schedule.every(30).minutes.do(da.run_dream_cycle)
    
    # Run once on startup
    da.run_dream_cycle()
    
    while True:
        schedule.run_pending()
        time.sleep(60) # Sleep longer since it's a slow job
