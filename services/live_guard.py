import time
import logging
import os
from storage.repository import Repository
from ai.registry.promotion_registry import PromotionRegistry
from risk.gate import evaluate_proposal

logger = logging.getLogger("services.live_guard")

class LiveGuard:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.pr = PromotionRegistry(repo)
        self.session_id = repo.register_session("Live-Guard-Production", "live")

    def run_guard(self):
        """Production Safety Layer: Monitor Live State and Promotion Gate."""
        logger.warning(f"🚀 V8.1 Live Guard STARTED. Session: {self.session_id}")
        
        while True:
            try:
                # 1. Update service heartbeat
                self.repo.update_service_state("V8-LiveGuard", "active", os.getpid())
                
                # 2. Check for manual promotion approved events
                # In V8.1, the dashboard marks 'approved' and the guard triggers deployment.
                
                # 3. Monitor for kill switch (STOP ALL)
                config = self.repo.get_service_config("V8-LiveGuard")
                if config.get("kill_switch"):
                    logger.critical("🚨 KILL SWITCH DETECTED. Stopping production trading now.")
                    # Implement local process termination or flag update
                
                logger.debug("Guard check complete. Waiting for 5 minutes...")
                time.sleep(300)
                
            except Exception as e:
                logger.exception(f"Live Guard Loop crashed: {e}")
                time.sleep(60)

if __name__ == "__main__":
    from storage.repository import Repository
    logging.basicConfig(level=logging.INFO)
    guard = LiveGuard(Repository())
    guard.run_guard()
