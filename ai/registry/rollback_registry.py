import logging
from datetime import datetime, timezone
from storage.repository import Repository

logger = logging.getLogger("ai.registry.rollback_registry")

class RollbackRegistry:
    def __init__(self, repo: Repository):
        self.repo = repo

    def rollback_live(self, reason: str):
        """Emergency rollback of the current live deployment to the previous stable version."""
        with self.repo._get_connection() as conn:
            # 1. Archive current
            conn.execute("UPDATE live_deployments SET status = 'rolled_back' WHERE status = 'active'")
            
            # 2. Get previous archived (the most recent one that isn't the current)
            prev = conn.execute(
                "SELECT * FROM live_deployments WHERE status = 'archived' ORDER BY deployed_at DESC LIMIT 1"
            ).fetchone()
            
            if prev:
                # 3. Re-deploy previous
                conn.execute(
                    "UPDATE live_deployments SET status = 'active' WHERE id = ?", (prev["id"],)
                )
                logger.warning(f"⚠️ ROLLBACK SUCCESS: Restored {prev['model_tag']} with reason: {reason}")
                conn.commit()
                return True
            else:
                logger.error("Rollback failed: No previous stable deployment found in registry.")
                return False

if __name__ == "__main__":
    from storage.repository import Repository
    rr = RollbackRegistry(Repository())
    print("Rollback registry initialized.")
