from typing import Dict, Any

class NvidiaTeacher:
    def __init__(self, repo):
        self.repo = repo

    def analyze(self) -> Dict[str, Any]:
        outcomes = self.repo.get_recent_outcomes(days=14)
        decisions = self.repo.get_recent_decisions(days=14)
        
        if not outcomes or not decisions:
            return {"findings": [], "max_drawdown": 0.0, "status": "insufficient_data"}

        dec_map = {d["id"]: d for d in decisions}
        
        # Calcolo Equity Drawdown corretto in ordine cronologico
        outcomes = sorted(outcomes, key=lambda x: x["closed_at"])
        equity = 1.0
        peak = 1.0
        true_max_dd = 0.0
        
        regime_losses = {}
        
        for o in outcomes:
            pnl = o.get("realized_pnl_pct", 0.0)
            equity *= (1.0 + pnl)
            if equity > peak:
                peak = equity
            dd = (equity - peak) / peak
            if dd < true_max_dd:
                true_max_dd = dd
                
            if pnl < 0:
                d = dec_map.get(o["decision_id"])
                if d and d.get("regime"):
                    r = d["regime"]
                    regime_losses[r] = regime_losses.get(r, 0) + 1

        findings = []
        for r, fails in regime_losses.items():
            if fails >= 2:
                findings.append({
                    "issue": f"Recurring losses in {r}",
                    "suggested_regime": r,
                    "edge": f"Stricter entry filtering required for {r}"
                })

        if true_max_dd < -0.05:
            findings.append({
                "issue": "Drawdown exceeded 5%",
                "suggested_regime": "ALL",
                "edge": "Implement strict ATR sizing constraint"
            })

        return {
            "findings": findings,
            "max_drawdown": true_max_dd,
            "status": "completed"
        }
