import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List

class SkillGenerator:
    def generate_from_findings(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates = []
        for f in analysis.get("findings", []):
            regime = f["suggested_regime"]
            skill = {
                "skill_id": f"SKL-{uuid.uuid4().hex[:8]}",
                "name": f"guard_{regime.lower()}",
                "version": "1.0.0",
                "market_regime": regime,
                "entry_conditions": [f"regime == '{regime}'", "consensus_score > 0.70"],
                "exit_conditions": ["pnl <= -0.02"],
                "risk_rules": ["daily_loss_limit = -0.03"],
                "position_sizing_rules": ["size_pct <= 0.15"],
                "block_conditions": [f"regime == '{regime}' and atr_5m > avg_atr"],
                "expected_edge": f["edge"],
                "validation_status": "candidate",
                "prompt_rule": f"RULE: In {regime} regime, apply strict entry: {f['edge']}",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            candidates.append(skill)
        return candidates
