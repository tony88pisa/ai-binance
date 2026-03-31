from typing import Dict, Any

class SkillValidator:
    def __init__(self, repo):
        self.repo = repo

    def validate(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        # Syntax check
        if not isinstance(skill.get("entry_conditions"), list):
            return self._fail("invalid entry_conditions syntax")

        # Duplicate check
        for existing in self.repo.list_skill_candidates():
            if existing["status"] == "approved" and existing["name"] == skill["name"]:
                return self._fail("duplicate skill name")

        # Backtest Locale su Dati Reali (Filtered by regime)
        # Importante: get_recent_outcomes è già ordinato cronologicamente ASC dal repository corretto
        outcomes = self.repo.get_recent_outcomes(days=14)
        decisions = self.repo.get_recent_decisions(days=14)
        
        regime = skill.get("market_regime")
        base_pnls = [o.get("realized_pnl_pct", 0) for o in outcomes]
        base_wr = (sum(1 for p in base_pnls if p > 0) / len(base_pnls)) * 100 if base_pnls else 50.0
        
        # Gestione del regime globale "ALL" per skill universali
        if regime == "ALL":
            dec_map = {d["id"]: d for d in decisions}
        else:
            dec_map = {d["id"]: d for d in decisions if d.get("regime") == regime}
            
        skill_outcomes = [o for o in outcomes if o["decision_id"] in dec_map]
        
        if len(skill_outcomes) < 3:
            return self._fail("insufficient trade count for target regime")

        # Calcolo drawdown cumulativo corretto per validazione reale
        pnls = [o.get("realized_pnl_pct", 0) for o in skill_outcomes]
        wins = sum(1 for p in pnls if p > 0)
        gross_profit = sum(p for p in pnls if p > 0)
        gross_loss = abs(sum(p for p in pnls if p < 0))
        
        equity = 1.0
        peak = 1.0
        true_max_dd = 0.0
        for p in pnls:
            equity *= (1.0 + p)
            if equity > peak:
                peak = equity
            dd = (equity - peak) / peak
            if dd < true_max_dd:
                true_max_dd = dd

        sim_wr = (wins / len(skill_outcomes)) * 100
        sim_pf = gross_profit / gross_loss if gross_loss > 0 else 2.0
        
        passed = sim_wr > base_wr and true_max_dd > -0.10
        
        return {
            "passed": passed,
            "win_rate": sim_wr,
            "avg_pnl": sum(pnls) / len(pnls),
            "max_drawdown": true_max_dd,
            "profit_factor": sim_pf,
            "trade_count": len(skill_outcomes),
            "regime_stability": "STABLE" if passed else "UNSTABLE",
            "reason": "Beats baseline in target regime" if passed else "Fails to beat baseline metrics"
        }

    def _fail(self, reason: str) -> Dict[str, Any]:
        return {
            "passed": False, "win_rate": 0, "avg_pnl": 0, "max_drawdown": 0,
            "profit_factor": 0, "trade_count": 0, "regime_stability": "N/A", "reason": reason
        }
