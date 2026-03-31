from typing import Dict, Any

class PromotionGate:
    def __init__(self, repo):
        self.repo = repo

    def evaluate(self, skill_id: str, val_metrics: Dict[str, Any]) -> bool:
        if not val_metrics.get("passed"):
            return False
            
        if val_metrics.get("max_drawdown", 0) < -0.10:
            return False
            
        if val_metrics.get("trade_count", 0) < 3:
            return False

        return True
