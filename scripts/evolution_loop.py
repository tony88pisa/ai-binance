"""
EVOLUTION LOOP V8.3 — Module 7 (Complete Orchestrator)
Autonomous TestLab learning cycle:
  1. Sync outcomes from Freqtrade dry-run
  2. Detect current market regime per-pair
  3. NVIDIA Teacher deep review
  4. Generate candidate strategies (regime-aware)
  5. Save to registry (CANDIDATE only, never auto-promote to live)
  6. Report to dashboard
"""
import sys
import os
import sqlite3
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from storage.repository import Repository
from ai.nvidia_client import NvidiaClient
from ai.regime_detector import RegimeDetector, MarketRegime, REGIME_STRATEGY_MAP

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("EVOLUTION_LOOP")

FT_DB_PATH = PROJECT_ROOT / "tradesv3.dryrun.sqlite"
MIN_TRADES_THRESHOLD = 5


class EvolutionLoop:
    def __init__(self):
        self.repo = Repository()
        self.nvidia = NvidiaClient()
        self.regime = RegimeDetector()
        self.run_summary = {
            "synced": 0, "outcomes_total": 0, "regime": "UNKNOWN",
            "nvidia_review": False, "candidates_generated": 0,
            "source": "none", "timestamp": ""
        }

    # ========== PHASE 1: SYNC OUTCOMES ==========
    def sync_outcomes(self):
        """Bridge Freqtrade closed trades with AI Decisions."""
        if not FT_DB_PATH.exists():
            logger.warning("Freqtrade DB not found. Skipping sync.")
            return 0
        synced = 0
        try:
            with sqlite3.connect(FT_DB_PATH) as ft_conn:
                ft_conn.row_factory = sqlite3.Row
                trades = ft_conn.execute(
                    "SELECT id, pair, profit_ratio, profit_abs, open_date, close_date, enter_tag "
                    "FROM trades WHERE is_open = 0"
                ).fetchall()
                for t in trades:
                    dec_id = t["enter_tag"]
                    if not dec_id or not dec_id.startswith("DEC-"):
                        continue
                    with self.repo._conn() as conn:
                        if conn.execute("SELECT 1 FROM trade_outcomes WHERE decision_id = ?", (dec_id,)).fetchone():
                            continue
                    self.repo.log_outcome({
                        "id": f"OUT-{t['id']}-{dec_id}",
                        "decision_id": dec_id,
                        "asset": t["pair"],
                        "open_at": t["open_date"],
                        "closed_at": t["close_date"],
                        "realized_pnl_pct": float(t["profit_ratio"]) * 100,
                        "realized_pnl_abs": float(t["profit_abs"]),
                        "was_profitable": bool(t["profit_ratio"] > 0)
                    })
                    synced += 1
        except Exception as e:
            logger.error(f"Sync error: {e}")
        if synced:
            logger.info(f"Synced {synced} new outcomes.")
        self.run_summary["synced"] = synced
        return synced

    # ========== PHASE 2: REGIME SNAPSHOT ==========
    def snapshot_regime(self):
        """Read latest regime from decisions table."""
        regime_label = MarketRegime.UNKNOWN
        try:
            with self.repo._conn() as conn:
                rows = conn.execute(
                    "SELECT market_regime FROM decisions WHERE market_regime IS NOT NULL "
                    "ORDER BY timestamp_utc DESC LIMIT 10"
                ).fetchall()
                if rows:
                    from collections import Counter
                    valid = [r["market_regime"].upper() for r in rows
                             if r["market_regime"] and r["market_regime"] != "unknown"]
                    if valid:
                        regime_label = Counter(valid).most_common(1)[0][0]
        except Exception as e:
            logger.error(f"Regime snapshot error: {e}")
        self.run_summary["regime"] = regime_label
        logger.info(f"Current global regime: {regime_label}")
        return regime_label

    # ========== PHASE 3: LOCAL ANALYSIS ==========
    def local_analysis(self, outcomes):
        """Analyze outcomes locally, generate candidates if toxic assets found."""
        candidates = 0
        if not outcomes:
            return candidates
        assets = {}
        for row in outcomes:
            a = row["asset"]
            if a not in assets:
                assets[a] = {"pnl": 0.0, "tot": 0}
            assets[a]["pnl"] += row["realized_pnl_abs"]
            assets[a]["tot"] += 1

        worst = min(assets.items(), key=lambda x: x[1]["pnl"])
        if worst[1]["pnl"] < -5.0:
            tag = f"Local-Filter-{int(time.time())}"
            rules = {
                "blocked_pairs": [worst[0]],
                "regime": self.run_summary["regime"],
                "reasoning": f"Asset {worst[0]}: {worst[1]['pnl']:.2f} USDC / {worst[1]['tot']} trades"
            }
            self.repo.register_strategy_version(tag, "LocalEvolution-V8.3", json.dumps(rules), "OllamaHybrid")
            logger.info(f"LOCAL candidate: {tag}")
            candidates += 1
        return candidates

    # ========== PHASE 4: NVIDIA TEACHER REVIEW ==========
    def nvidia_review(self, outcomes):
        """Send outcomes to NVIDIA Teacher for deep review."""
        candidates = 0
        if not self.nvidia.enabled or not self.nvidia.api_key:
            logger.info("NVIDIA Teacher disabled or no API key.")
            return candidates

        batch = [dict(o) for o in outcomes[:20]]
        review = self.nvidia.review_closed_trades(batch)
        if not review:
            logger.warning("NVIDIA Teacher returned no review.")
            return candidates

        # Save review
        rev_id = f"REV-NV-{int(time.time())}"
        self.repo.log_nvidia_review({
            "review_id": rev_id,
            "reviewed_period": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "dominant_failures": review.get("dominant_failures"),
            "confidence_miscalibration": review.get("confidence_miscalibration"),
            "regime_findings": review.get("regime_findings"),
            "prompt_corrections": review.get("prompt_corrections"),
            "rule_corrections": review.get("rule_corrections"),
            "candidate_strategies": review.get("candidate_strategies"),
            "suggested_labels": review.get("suggested_labels"),
            "risk_notes": review.get("risk_notes"),
            "token_usage": 4500
        })
        logger.info(f"NVIDIA review saved: {rev_id}")
        self.run_summary["nvidia_review"] = True

        # Register NVIDIA candidate strategies
        for i, cand in enumerate(review.get("candidate_strategies", [])):
            tag = f"STRAT-NV-{int(time.time())}-{i}"
            cand["regime_context"] = self.run_summary["regime"]
            self.repo.register_strategy_version(tag, "NvidiaTeacher-V8.3", json.dumps(cand), "OllamaHybrid")
            logger.info(f"NVIDIA candidate registered: {tag}")
            candidates += 1
        return candidates

    # ========== PHASE 5: REGIME-AWARE CANDIDATE ==========
    def regime_candidate(self):
        """Generate a regime-aware candidate from the strategy map."""
        regime = self.run_summary["regime"]
        if regime in REGIME_STRATEGY_MAP:
            params = REGIME_STRATEGY_MAP[regime]
            tag = f"Regime-{regime}-{int(time.time())}"
            self.repo.register_strategy_version(
                tag, params["family"],
                json.dumps({"regime": regime, **params}),
                "RegimeDetector-V8.3"
            )
            logger.info(f"Regime candidate: {tag} ({regime})")
            return 1
        return 0

    # ========== PHASE 6: UPDATE DASHBOARD STATE ==========
    def update_dashboard_state(self):
        """Write final evolution state to service_state for dashboard."""
        self.run_summary["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Count total candidates in registry
        with self.repo._conn() as conn:
            row = conn.execute("SELECT COUNT(*) as c FROM strategy_versions WHERE status='candidate'").fetchone()
            total_candidates = row["c"] if row else 0

        source = "hybrid" if self.run_summary["nvidia_review"] else "local"
        self.run_summary["source"] = source

        self.repo.update_service_state("evolution_loop", "review_conclusa", os.getpid(), {
            "phase": "Evolution V8.3 Completata",
            "last_run": self.run_summary["timestamp"],
            "outcomes_total": self.run_summary["outcomes_total"],
            "synced_this_run": self.run_summary["synced"],
            "regime": self.run_summary["regime"],
            "nvidia_review": self.run_summary["nvidia_review"],
            "candidates_generated": self.run_summary["candidates_generated"],
            "total_candidates": total_candidates,
            "source": source,
            "guardrail": "CANDIDATE_ONLY — no auto-promote to live"
        })
        logger.info(f"Dashboard state updated. Total candidates: {total_candidates}, Source: {source}")

    # ========== ORCHESTRATOR ==========
    def run_once(self):
        """Execute one full evolution cycle."""
        logger.info("=" * 60)
        logger.info("EVOLUTION LOOP V8.3 — Starting cycle")
        logger.info("=" * 60)

        # Phase 1
        self.sync_outcomes()

        # Phase 2
        self.snapshot_regime()

        # Phase 3-5: Gather outcomes and analyze
        with self.repo._conn() as conn:
            outcomes = conn.execute("SELECT * FROM trade_outcomes").fetchall()
            self.run_summary["outcomes_total"] = len(outcomes)

        total_candidates = 0

        # Phase 3: Local
        total_candidates += self.local_analysis(outcomes if outcomes else [])

        # Phase 4: NVIDIA
        total_candidates += self.nvidia_review(outcomes if outcomes else [])

        # Phase 5: Regime-aware
        total_candidates += self.regime_candidate()

        self.run_summary["candidates_generated"] = total_candidates

        # Phase 6: Dashboard
        self.update_dashboard_state()

        logger.info("=" * 60)
        logger.info(f"CYCLE COMPLETE | Candidates: {total_candidates} | Regime: {self.run_summary['regime']} | Source: {self.run_summary['source']}")
        logger.info("GUARDRAIL: All strategies are CANDIDATE only. No auto-promotion.")
        logger.info("=" * 60)
        return self.run_summary


if __name__ == "__main__":
    loop = EvolutionLoop()
    result = loop.run_once()
    print(json.dumps(result, indent=2, default=str))
