"""
VALIDATION GATE V8.3 — Module 8
Validates candidate strategies against objective metrics before promotion.
No candidate can reach live without passing this gate.

Metrics:
  - Win Rate (minimum 45%)
  - Max Drawdown (maximum -15%)
  - Sharpe Ratio (minimum 0.5)

Outcomes: validated / rejected / keep_candidate
Promotion: MANUAL ONLY — no auto-promote
"""
import sys
import json
import logging
import time
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from storage.repository import Repository

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("VALIDATION_GATE")


# === PROMOTION CRITERIA (HARD RULES) ===
VALIDATION_CRITERIA = {
    "min_win_rate": 0.45,        # 45% minimum
    "max_drawdown": -0.15,       # -15% maximum
    "min_sharpe": 0.5,           # 0.5 minimum
    "min_trades": 3,             # At least 3 trades to evaluate
    "auto_promote": False,       # NEVER auto-promote
    "require_manual_approval": True,
}


class ValidationGate:
    def __init__(self):
        self.repo = Repository()

    def validate_all_candidates(self) -> List[Dict]:
        """Run validation on all candidate strategies."""
        logger.info("=" * 60)
        logger.info("VALIDATION GATE V8.3 — Starting validation cycle")
        logger.info("=" * 60)

        results = []
        with self.repo._get_connection() as conn:
            candidates = conn.execute(
                "SELECT version_tag, family, rules_json, created_at "
                "FROM strategy_versions WHERE status = 'candidate' "
                "ORDER BY created_at DESC"
            ).fetchall()

        logger.info(f"Found {len(candidates)} candidate strategies to validate.")

        for cand in candidates:
            tag = cand["version_tag"]
            family = cand["family"]
            rules = json.loads(cand["rules_json"]) if cand["rules_json"] else {}

            result = self._validate_candidate(tag, family, rules)
            results.append(result)

            # Save validation run to DB
            self._save_validation_run(result)

            # Update strategy status based on result
            self._update_strategy_status(result)

        # Update dashboard state
        self._update_dashboard(results)

        logger.info("=" * 60)
        validated = sum(1 for r in results if r["verdict"] == "validated")
        rejected = sum(1 for r in results if r["verdict"] == "rejected")
        kept = sum(1 for r in results if r["verdict"] == "keep_candidate")
        logger.info(f"RESULTS: {validated} validated, {rejected} rejected, {kept} kept")
        logger.info(f"GUARDRAIL: auto_promote={VALIDATION_CRITERIA['auto_promote']}")
        logger.info("=" * 60)

        return results

    def _validate_candidate(self, tag: str, family: str, rules: dict) -> Dict:
        """Validate a single candidate strategy against metrics."""
        logger.info(f"Validating: {tag} ({family})")

        # Fetch trade outcomes matching this strategy's context
        metrics = self._compute_metrics(tag, family, rules)

        # Apply criteria
        verdict = self._apply_criteria(metrics)

        return {
            "version_tag": tag,
            "family": family,
            "win_rate": metrics["win_rate"],
            "max_drawdown": metrics["max_drawdown"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "num_trades": metrics["num_trades"],
            "total_pnl": metrics["total_pnl"],
            "verdict": verdict,
            "criteria": VALIDATION_CRITERIA.copy(),
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _compute_metrics(self, tag: str, family: str, rules: dict) -> Dict:
        """Compute validation metrics from available trade outcomes."""
        metrics = {
            "win_rate": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "num_trades": 0,
            "total_pnl": 0.0,
        }

        with self.repo._get_connection() as conn:
            # Get all outcomes (in dry-run we use global outcomes as proxy)
            outcomes = conn.execute(
                "SELECT realized_pnl_pct, realized_pnl_abs, was_profitable "
                "FROM trade_outcomes ORDER BY closed_at"
            ).fetchall()

            if not outcomes:
                return metrics

            pnl_list = [float(o["realized_pnl_pct"]) for o in outcomes]
            abs_list = [float(o["realized_pnl_abs"]) for o in outcomes]
            wins = sum(1 for o in outcomes if o["was_profitable"])

            metrics["num_trades"] = len(outcomes)
            metrics["win_rate"] = wins / len(outcomes) if outcomes else 0.0
            metrics["total_pnl"] = sum(abs_list)

            # Max Drawdown (cumulative)
            if pnl_list:
                cumulative = np.cumsum(pnl_list)
                peak = np.maximum.accumulate(cumulative)
                drawdowns = cumulative - peak
                metrics["max_drawdown"] = float(np.min(drawdowns)) / 100.0 if len(drawdowns) > 0 else 0.0

            # Sharpe Ratio (simplified: mean/std of returns)
            if len(pnl_list) >= 2:
                mean_ret = np.mean(pnl_list)
                std_ret = np.std(pnl_list)
                metrics["sharpe_ratio"] = float(mean_ret / std_ret) if std_ret > 0 else 0.0

            # Apply strategy-specific filters from rules
            blocked = rules.get("blocked_pairs", [])
            if blocked:
                # Filter outcomes for blocked pairs
                filtered = conn.execute(
                    "SELECT realized_pnl_pct, was_profitable FROM trade_outcomes "
                    "WHERE asset NOT IN ({})".format(",".join(f"'{p}'" for p in blocked))
                ).fetchall()
                if filtered:
                    f_wins = sum(1 for o in filtered if o["was_profitable"])
                    metrics["win_rate"] = f_wins / len(filtered)

        return metrics

    def _apply_criteria(self, metrics: Dict) -> str:
        """Apply hard validation criteria. Returns verdict."""
        if metrics["num_trades"] < VALIDATION_CRITERIA["min_trades"]:
            return "keep_candidate"  # Not enough data to judge

        passed = 0
        total = 3

        if metrics["win_rate"] >= VALIDATION_CRITERIA["min_win_rate"]:
            passed += 1
        if metrics["max_drawdown"] >= VALIDATION_CRITERIA["max_drawdown"]:
            passed += 1
        if metrics["sharpe_ratio"] >= VALIDATION_CRITERIA["min_sharpe"]:
            passed += 1

        if passed == total:
            return "validated"
        elif passed >= 2:
            return "keep_candidate"  # Close but not ready
        else:
            return "rejected"

    def _save_validation_run(self, result: Dict):
        """Persist validation result to validation_runs table."""
        with self.repo._get_connection() as conn:
            run_id = f"VAL-{int(time.time())}-{result['version_tag'][:20]}"
            conn.execute(
                "INSERT OR REPLACE INTO validation_runs "
                "(id, model_tag, win_rate, max_drawdown, sharpe_ratio, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, result["version_tag"], result["win_rate"],
                 result["max_drawdown"], result["sharpe_ratio"],
                 result["validated_at"])
            )
            conn.commit()

    def _update_strategy_status(self, result: Dict):
        """Update strategy status based on validation verdict."""
        new_status = result["verdict"]  # validated, rejected, or keep_candidate
        if new_status == "keep_candidate":
            new_status = "candidate"  # Keep as-is in DB

        with self.repo._get_connection() as conn:
            conn.execute(
                "UPDATE strategy_versions SET status = ? WHERE version_tag = ?",
                (new_status, result["version_tag"])
            )
            conn.commit()
        logger.info(f"  -> {result['version_tag']}: {result['verdict']} "
                     f"(WR={result['win_rate']:.0%}, DD={result['max_drawdown']:.2%}, "
                     f"SR={result['sharpe_ratio']:.2f})")

    def _update_dashboard(self, results: List[Dict]):
        """Update service_state for dashboard display."""
        import os
        summary = {
            "phase": "Validation Gate V8.3",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "total_validated": sum(1 for r in results if r["verdict"] == "validated"),
            "total_rejected": sum(1 for r in results if r["verdict"] == "rejected"),
            "total_kept": sum(1 for r in results if r["verdict"] == "keep_candidate"),
            "total_candidates": len(results),
            "auto_promote": False,
            "promotion": "MANUAL_ONLY",
            "results": [{
                "tag": r["version_tag"][:30],
                "family": r["family"][:25],
                "verdict": r["verdict"],
                "win_rate": round(r["win_rate"] * 100, 1),
                "drawdown": round(r["max_drawdown"] * 100, 2),
                "sharpe": round(r["sharpe_ratio"], 2),
            } for r in results[:10]],  # Top 10 for dashboard
        }
        self.repo.update_service_state(
            "validation_gate", "completed", os.getpid(), summary
        )


if __name__ == "__main__":
    gate = ValidationGate()
    results = gate.validate_all_candidates()
    print("\n=== VALIDATION RESULTS ===")
    for r in results:
        print(f"{r['version_tag']:40s} | {r['verdict']:15s} | "
              f"WR={r['win_rate']:.0%} DD={r['max_drawdown']:.2%} SR={r['sharpe_ratio']:.2f}")
    print(f"\nPROMOTION: MANUAL ONLY (auto_promote=False)")
