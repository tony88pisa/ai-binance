import logging
from datetime import datetime, timezone
from storage.repository import Repository

logger = logging.getLogger("ai.registry.promotion_registry")

class PromotionRegistry:
    def __init__(self, repo: Repository):
        self.repo = repo

    def promote_to_live(self, model_tag: str, strategy_tag: str, approved_by: str):
        """Final promotion gate: pushes a model/strategy pair from Lab to Live."""
        # 1. Validation check (must be 'validated')
        with self.repo._get_connection() as conn:
            model = conn.execute("SELECT status FROM model_versions WHERE tag_name = ?", (model_tag,)).fetchone()
            if not model or model["status"] not in ["validated", "candidate"]:
                logger.error(f"Promotion failed: Model {model_tag} is not validated.")
                return False
            
            # 2. Execute transition
            self.repo.deploy_to_live(
                model_tag=model_tag, 
                strategy_tag=strategy_tag, 
                deployed_by=approved_by
            )
            
            # 3. Update version status
            conn.execute("UPDATE model_versions SET status = 'live' WHERE tag_name = ?", (model_tag,))
            conn.execute("UPDATE strategy_versions SET status = 'live' WHERE version_tag = ?", (strategy_tag,))
            conn.commit()
            
        logger.warning(f"🚀 PROMOTION SUCCESS: {model_tag} with strategy {strategy_tag} now LIVE.")
        return True

if __name__ == "__main__":
    from storage.repository import Repository
    pr = PromotionRegistry(Repository())
    print("Promotion logic initialized.")
