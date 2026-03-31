"""
Memory Manager — structured logging, retrieval, and evaluation.

Responsibilities:
1. LOG decisions and outcomes with full context
2. RETRIEVE relevant past outcomes for prompt injection (partitioned by asset/regime)
3. EVALUATE decision quality over time (win rate, confidence calibration)
4. PERSIST state atomically to JSON

This is NOT:
- Machine learning
- Model training
- Reinforcement learning
- Bayesian optimization
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from memory.types import (
    DecisionRecord, EvaluationSummary, EventRecord,
    MemoryStore, OutcomeRecord,
)

logger = logging.getLogger("memory.manager")

DEFAULT_MEMORY_PATH = Path(__file__).resolve().parent.parent / "user_data" / "memory_v2.json"

MAX_DECISIONS = 200
MAX_OUTCOMES = 200
MAX_EVENTS = 100


class MemoryManager:
    """Structured memory with partitioned retrieval and honest evaluation."""

    def __init__(self, path: Path = DEFAULT_MEMORY_PATH):
        self.path = path
        self._store: MemoryStore = self._load()
        self._decision_counter = len(self._store.decisions)

    # ================================================================
    # LAYER 1: EVENT LOGGING
    # ================================================================

    def log_event(self, event_type: str, message: str, **data) -> None:
        """Append a system event. Never crashes."""
        try:
            record = EventRecord(
                event_type=event_type, message=message, data=data
            )
            self._store.events.append(record.to_dict())
            self._store.events = self._store.events[-MAX_EVENTS:]
            self._save()
        except Exception as e:
            logger.error(f"Event log failed: {e}")

    # ================================================================
    # LAYER 2: DECISION LOGGING
    # ================================================================

    def log_decision(self, record: DecisionRecord) -> str:
        """Log an AI decision with full context. Returns decision ID."""
        try:
            self._store.decisions.append(record.to_dict())
            self._store.decisions = self._store.decisions[-MAX_DECISIONS:]
            self._save()
            logger.debug(f"Decision logged: {record.id} {record.asset} {record.action}")
            return record.id
        except Exception as e:
            logger.error(f"Decision log failed: {e}")
            return ""

    def generate_decision_id(self) -> str:
        """Generate unique decision ID."""
        self._decision_counter += 1
        ts = datetime.now(timezone.utc).strftime("%Y%m%d")
        return f"D-{ts}-{self._decision_counter:04d}"

    # ================================================================
    # LAYER 3: OUTCOME LOGGING
    # ================================================================

    def log_outcome(self, record: OutcomeRecord) -> None:
        """Log a trade outcome linked to a decision."""
        try:
            self._store.outcomes.append(record.to_dict())
            self._store.outcomes = self._store.outcomes[-MAX_OUTCOMES:]
            self._save()
            logger.debug(
                f"Outcome logged: {record.decision_id} {record.asset} "
                f"pnl={record.realized_pnl_pct:+.2f}%"
            )
        except Exception as e:
            logger.error(f"Outcome log failed: {e}")

    # ================================================================
    # LAYER 4: RETRIEVAL (partitioned, NOT learning)
    # ================================================================

    def get_relevant_outcomes(
        self,
        asset: str,
        market_regime: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """Retrieve past outcomes relevant to the current context.

        Partition logic:
        1. Filter by asset first
        2. If market_regime provided, prefer outcomes from same regime
        3. Fall back to most recent if no matches
        """
        all_outcomes = self._store.outcomes

        # Filter by asset
        asset_base = asset.split('/')[0] if '/' in asset else asset
        asset_outcomes = [
            o for o in all_outcomes
            if asset_base.lower() in o.get("asset", "").lower()
        ]

        # If regime filter, prefer same regime
        if market_regime and asset_outcomes:
            regime_outcomes = [
                o for o in asset_outcomes
                if o.get("market_regime_at_exit", "") == market_regime
            ]
            if regime_outcomes:
                return regime_outcomes[-limit:]

        if asset_outcomes:
            return asset_outcomes[-limit:]

        # Fallback: most recent from any asset
        return all_outcomes[-limit:]

    def format_for_prompt(
        self,
        asset: str,
        market_regime: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """Format relevant outcomes for injection into AI prompt.

        This is RETRIEVAL, not learning. The model does not update weights.
        Past outcomes are presented as context for the model to reason about.
        """
        outcomes = self.get_relevant_outcomes(asset, market_regime, limit)

        if not outcomes:
            return "[MEMORY] No past outcomes recorded yet."

        lines = ["[MEMORY] Past outcomes for context (retrieval, not training):"]
        for o in outcomes:
            pnl = o.get("realized_pnl_pct", 0)
            conf = o.get("confidence_at_entry", 0)
            reason = o.get("entry_thesis", "")[:60]
            regime = o.get("market_regime_at_exit", "?")
            symbol = "✅" if o.get("was_profitable", False) else "❌"
            lines.append(
                f"  {symbol} {o.get('asset','?')} pnl={pnl:+.1f}% conf={conf} "
                f"regime={regime} | {reason}"
            )
        return "\n".join(lines)

    # ================================================================
    # LAYER 5: EVALUATION (measurement, NOT optimization)
    # ================================================================

    def compute_evaluation(self) -> EvaluationSummary:
        """Compute honest performance metrics from logged outcomes.

        This is EVALUATION — measuring quality.
        It does not modify any model or parameter.
        """
        outcomes = self._store.outcomes
        decisions = self._store.decisions

        total_decided = len(decisions)
        executed = [o for o in outcomes if o.get("realized_pnl_pct") is not None]
        profitable = [o for o in executed if o.get("was_profitable", False)]
        losing = [o for o in executed if not o.get("was_profitable", False)]

        win_rate = len(profitable) / len(executed) if executed else 0.0

        avg_conf_w = (
            sum(o.get("confidence_at_entry", 0) for o in profitable) / len(profitable)
            if profitable else 0.0
        )
        avg_conf_l = (
            sum(o.get("confidence_at_entry", 0) for o in losing) / len(losing)
            if losing else 0.0
        )

        avg_pnl = (
            sum(o.get("realized_pnl_pct", 0) for o in executed) / len(executed)
            if executed else 0.0
        )
        avg_hold = (
            sum(o.get("hold_duration_minutes", 0) for o in executed) / len(executed)
            if executed else 0.0
        )

        # Calibration assessment
        if executed and len(executed) >= 5:
            if avg_conf_w > 70 and win_rate < 0.4:
                calibration = "overconfident"
            elif avg_conf_w < 50 and win_rate > 0.6:
                calibration = "underconfident"
            else:
                calibration = "calibrated"
        else:
            calibration = "insufficient_data"

        # Per-asset breakdown
        per_asset: dict[str, dict] = {}
        asset_groups: dict[str, list] = defaultdict(list)
        for o in executed:
            a = o.get("asset", "?").split("/")[0]
            asset_groups[a].append(o)
        for a, group in asset_groups.items():
            wins = [o for o in group if o.get("was_profitable")]
            per_asset[a] = {
                "trades": len(group),
                "win_rate": len(wins) / len(group) if group else 0,
                "avg_pnl": sum(o.get("realized_pnl_pct", 0) for o in group) / len(group),
            }

        # Per-regime breakdown
        per_regime: dict[str, dict] = {}
        regime_groups: dict[str, list] = defaultdict(list)
        for o in executed:
            r = o.get("market_regime_at_exit", "unknown")
            regime_groups[r].append(o)
        for r, group in regime_groups.items():
            wins = [o for o in group if o.get("was_profitable")]
            per_regime[r] = {
                "trades": len(group),
                "win_rate": len(wins) / len(group) if group else 0,
                "avg_pnl": sum(o.get("realized_pnl_pct", 0) for o in group) / len(group),
            }

        summary = EvaluationSummary(
            total_decisions=total_decided,
            total_executed=len(executed),
            total_profitable=len(profitable),
            total_losing=len(losing),
            win_rate=round(win_rate, 3),
            avg_confidence_winners=round(avg_conf_w, 1),
            avg_confidence_losers=round(avg_conf_l, 1),
            avg_pnl_pct=round(avg_pnl, 3),
            avg_hold_minutes=round(avg_hold, 1),
            confidence_calibration=calibration,
            per_asset=per_asset,
            per_regime=per_regime,
        )

        # Save evaluation
        self._store.evaluation = summary.to_dict()
        self._save()

        return summary

    # ================================================================
    # PERSISTENCE
    # ================================================================

    def _load(self) -> MemoryStore:
        """Load memory from disk."""
        try:
            if self.path.exists():
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("version", 1) >= 2:
                    return MemoryStore(**data)
                # V1 migration: old format with lessons_learned
                logger.info("Migrating memory from V1 to V2")
                return self._migrate_v1(data)
        except Exception as e:
            logger.error(f"Memory load failed, starting fresh: {e}")
        return MemoryStore()

    def _save(self) -> None:
        """Save memory atomically."""
        try:
            self._store.updated_at = datetime.now(timezone.utc).isoformat()
            data = self._store.to_json()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(data)
                if self.path.exists():
                    self.path.unlink()
                os.rename(tmp, str(self.path))
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception as e:
            logger.error(f"Memory save failed: {e}")

    def _migrate_v1(self, old_data: dict) -> MemoryStore:
        """Migrate V1 (lessons_learned) to V2 (structured layers)."""
        store = MemoryStore()
        for lesson in old_data.get("lessons_learned", []):
            # Convert old lessons to outcome records
            outcome = OutcomeRecord(
                decision_id="migrated",
                asset=lesson.get("action", "").replace("BUY ", ""),
                realized_pnl_pct=lesson.get("profit", 0.0),
                was_profitable=lesson.get("profit", 0) > 0,
                entry_thesis=lesson.get("lesson", "")[:100],
                confidence_at_entry=0,
            )
            store.outcomes.append(outcome.to_dict())
        return store
