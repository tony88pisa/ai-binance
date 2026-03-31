import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
from storage.repository import Repository

logger = logging.getLogger("ai.registry.strategy_registry")

class StrategyRegistry:
    def __init__(self, repo: Repository):
        self.repo = repo

    def register_strategy_version(self, family: str, rules: Dict, parent: Optional[str] = None) -> str:
        """Register a new strategy version (set of entry/exit filters)."""
        version_tag = f"STRAT-{family.upper()}-{int(datetime.now(timezone.utc).timestamp())}"
        with self.repo._get_connection() as conn:
            conn.execute(
                """INSERT INTO strategy_versions (version_tag, parent_tag, family, rules_json, created_at, status)
                   VALUES (?, ?, ?, ?, ?, 'candidate')""",
                (version_tag, parent or "", family, json.dumps(rules), 
                 datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
        logger.info(f"Strategy {version_tag} registered as candidate.")
        return version_tag

    def get_rules_for_version(self, version_tag: str) -> Dict:
        with self.repo._get_connection() as conn:
            row = conn.execute("SELECT rules_json FROM strategy_versions WHERE version_tag = ?", (version_tag,)).fetchone()
            return json.loads(row["rules_json"]) if row else {}

    def list_candidates(self) -> List[Dict]:
        with self.repo._get_connection() as conn:
            rows = conn.execute("SELECT * FROM strategy_versions WHERE status = 'candidate'").fetchall()
            return [dict(r) for r in rows]

if __name__ == "__main__":
    from storage.repository import Repository
    sr = StrategyRegistry(Repository())
    tag = sr.register_strategy_version("trend_follow", {"rsi_buy": 35, "macd_buy": 0.001})
    print(f"Registered: {tag}")
