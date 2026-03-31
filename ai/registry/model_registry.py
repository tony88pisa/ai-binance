import logging
from datetime import datetime, timezone
from typing import Optional, Dict
from storage.repository import Repository

logger = logging.getLogger("ai.registry.model_registry")

class ModelRegistry:
    def __init__(self, repo: Repository):
        self.repo = repo

    def register_new_model(self, tag: str, base: str, dataset_id: str, metrics: Dict, parent: Optional[str] = None):
        """Register a newly trained model version."""
        self.repo.register_model_version(
            tag=tag, 
            parent=parent or "", 
            base=base, 
            dataset_id=dataset_id, 
            metrics=metrics
        )
        logger.info(f"Model {tag} registered in registry.")

    def get_active_model(self, env: str) -> str:
        """Resolve the current active model for the given environment."""
        model = self.repo.get_active_model_for_env(env)
        return model if model else "qwen3:8b" # Absolute fallback

    def mark_model_rejected(self, tag: str):
        with self.repo._get_connection() as conn:
            conn.execute("UPDATE model_versions SET status = 'rejected' WHERE tag_name = ?", (tag,))
            conn.commit()
        logger.warning(f"Model {tag} marked as REJECTED.")

if __name__ == "__main__":
    from storage.repository import Repository
    mr = ModelRegistry(Repository())
    print(f"Active Live Model: {mr.get_active_model('live')}")
    print(f"Active Lab Model: {mr.get_active_model('testlab')}")
