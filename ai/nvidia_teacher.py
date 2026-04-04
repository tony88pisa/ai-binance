from typing import Dict, Any

class NvidiaTeacher:
    def __init__(self, repo):
        self.repo = repo

    def analyze(self) -> Dict[str, Any]:
        outcomes = self.repo.get_recent_outcomes(days=14)
        decisions = self.repo.get_recent_decisions(days=14)
        
        findings = []
        status = "insufficient_data"

        # 1. Analisi Trade Outcomes (Standard)
        if outcomes and decisions:
            dec_map = {d["id"]: d for d in decisions}
            outcomes = sorted(outcomes, key=lambda x: x["closed_at"])
            equity, peak, true_max_dd = 1.0, 1.0, 0.0
            regime_losses = {}

            for o in outcomes:
                pnl = o.get("realized_pnl_pct", 0.0)
                equity *= (1.0 + pnl)
                if equity > peak: peak = equity
                dd = (equity - peak) / peak
                if dd < true_max_dd: true_max_dd = dd
                if pnl < 0:
                    d = dec_map.get(o["decision_id"])
                    if d and d.get("regime"):
                        r = d["regime"]
                        regime_losses[r] = regime_losses.get(r, 0) + 1

            for r, fails in regime_losses.items():
                if fails >= 2:
                    findings.append({"issue": f"Recurring losses in {r}", "suggested_regime": r, "edge": f"Stricter entry filtering for {r}"})
            status = "completed"

        # 2. COLD START: Analisi Esplorativa (Missed Opportunities)
        if not findings:
            snapshots = self.repo.get_latest_snapshots()
            for s in snapshots:
                rsi_val = float(s.get("rsi_5m") if s.get("rsi_5m") is not None else 50.0)
                regime = s.get("regime") or "momentum"
                findings.append({
                    "issue": f"Exploratory analysis on {s['asset']}",
                    "suggested_regime": regime,
                    "edge": f"Optimize RSI entry threshold ({rsi_val:.1f}) for {regime}"
                })
            if findings: status = "exploratory_active"

        return {
            "findings": findings,
            "max_drawdown": 0.0 if not outcomes else true_max_dd,
            "status": status
        }
