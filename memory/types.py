"""
Memory system types — honest, structured, non-misleading.

TERMINOLOGY GUIDE (enforced throughout the codebase):
- EVENT LOG:       Raw timestamped record of something that happened. Append-only.
- DECISION LOG:    Record of an AI decision with full context at decision time.
- OUTCOME LOG:     Post-trade results linked back to the decision that caused them.
- RETRIEVAL:       Querying past records to inform future prompts. NOT learning.
- EVALUATION:      Measuring decision quality over time. NOT optimization.
- OPTIMIZATION:    Adjusting parameters based on evaluation. NOT YET IMPLEMENTED.
- TRAINING:        Updating model weights. NOT IMPLEMENTED. NOT CLAIMED.

What this system does:
  ✅ Logs decisions and outcomes structurally
  ✅ Retrieves relevant past outcomes for prompt injection
  ✅ Evaluates win rate, accuracy, and confidence calibration
  ✅ Partitions by asset, strategy, and regime

What this system does NOT do:
  ❌ Reinforcement learning
  ❌ Model fine-tuning
  ❌ Gradient updates
  ❌ Bayesian optimization
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class LogType(str, Enum):
    DECISION = "decision"
    OUTCOME = "outcome"
    EVENT = "event"


@dataclass
class DecisionRecord:
    """Snapshot of an AI decision at the moment it was made."""
    id: str                             # Unique ID (e.g. "D-20260328-001")
    timestamp_utc: str
    asset: str
    strategy: str = "YieldAggregatorAI"
    timeframe: str = "5m"

    # Decision
    action: str = "hold"                # buy | hold
    confidence: int = 0
    thesis: str = ""
    technical_basis: list[str] = field(default_factory=list)
    news_basis: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)

    # Context at decision time
    rsi_5m: float = 50.0
    macd_5m: float = 0.0
    rsi_1h: float = 50.0
    market_regime: str = "unknown"
    fear_greed_value: int = 50
    data_quality: str = "low"
    macro_risk_level: float = 0.5

    # Risk gate
    risk_approved: bool = False
    risk_verdict: str = ""              # approved | reduced | blocked
    approved_stake: float = 0.0

    # Execution
    was_executed: bool = False
    entry_price: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OutcomeRecord:
    """Post-trade outcome linked to a DecisionRecord."""
    decision_id: str                    # Links back to DecisionRecord.id
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    asset: str = ""
    strategy: str = "YieldAggregatorAI"

    # Execution results
    entry_price: float = 0.0
    exit_price: float = 0.0
    realized_pnl_pct: float = 0.0      # percentage
    realized_pnl_abs: float = 0.0      # absolute (€)
    hold_duration_minutes: float = 0.0
    stake_amount: float = 0.0

    # Excursion analysis
    max_adverse_excursion_pct: float = 0.0    # Worst drawdown during trade
    max_favorable_excursion_pct: float = 0.0  # Best profit during trade

    # Context at exit
    exit_reason: str = ""               # stoploss | roi | signal | trailing_stop
    market_regime_at_exit: str = "unknown"

    # Post-trade assessment
    was_profitable: bool = False
    confidence_at_entry: int = 0
    entry_thesis: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EventRecord:
    """Generic system event. Not a trade, not a decision."""
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str = ""                # circuit_breaker | daemon_cycle | model_error | startup
    message: str = ""
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationSummary:
    """Aggregated performance evaluation. NOT learning — just measurement."""
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_decisions: int = 0
    total_executed: int = 0
    total_profitable: int = 0
    total_losing: int = 0
    win_rate: float = 0.0               # profitable / executed
    avg_confidence_winners: float = 0.0
    avg_confidence_losers: float = 0.0
    avg_pnl_pct: float = 0.0
    avg_hold_minutes: float = 0.0
    confidence_calibration: str = ""    # e.g. "overconfident" | "underconfident" | "calibrated"

    # Per-asset breakdown
    per_asset: dict[str, dict] = field(default_factory=dict)
    # Per-regime breakdown
    per_regime: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MemoryStore:
    """Complete memory state. Written atomically."""
    version: int = 2
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    decisions: list[dict] = field(default_factory=list)
    outcomes: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    evaluation: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)
