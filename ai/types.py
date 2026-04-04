"""
Shared types and contracts for inter-module communication.

All agents and modules communicate through these typed structures.
This is the foundation for the entire system; every other module depends on it.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Action(str, Enum):
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    BLOCK = "block"
    WATCH = "watch"


class TaskType(str, Enum):
    RESEARCH = "research"
    ANALYSIS = "analysis"
    DECISION = "decision"
    RISK = "risk"
    EXECUTION = "execution"
    MONITORING = "monitoring"


class Status(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    BLOCKED = "blocked"
    FAILED = "failed"


class RiskVerdict(str, Enum):
    APPROVED = "approved"
    REDUCED = "reduced"
    BLOCKED = "blocked"


@dataclass
class AgentMessage:
    """Standard message contract between all agents/modules."""
    agent_name: str
    task_type: TaskType
    status: Status
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    asset: Optional[str] = None
    timeframe: Optional[str] = None
    confidence: int = 0
    inputs_used: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    recommended_action: Action = Action.HOLD
    reason_short: str = ""
    reason_full: str = ""
    requires_human_review: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["task_type"] = self.task_type.value
        d["status"] = self.status.value
        d["recommended_action"] = self.recommended_action.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> AgentMessage:
        data = data.copy()
        data["task_type"] = TaskType(data.get("task_type", "monitoring"))
        data["status"] = Status(data.get("status", "success"))
        data["recommended_action"] = Action(data.get("recommended_action", "hold"))
        return cls(**data)


@dataclass
class MarketIntelligence:
    """Pre-computed market intelligence for a single asset.
    Produced by the research layer, consumed by the decision layer."""
    asset: str
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Technical indicators (5m)
    rsi_5m: float = 50.0
    macd_5m: float = 0.0
    ema_20_5m: float = 0.0
    ema_50_5m: float = 0.0

    # Technical indicators (1h)
    rsi_1h: float = 50.0
    macd_1h: float = 0.0

    # Price
    open_price: float = 0.0
    close_price: float = 0.0

    # Sentiment (from research daemon)
    fear_and_greed: str = "N/A"
    fear_and_greed_value: int = 50
    market_regime: str = "unknown"
    news_sentiment_score: float = 0.0
    news_summary: str = ""
    news_count: int = 0
    top_headlines: list[str] = field(default_factory=list)
    macro_risk_level: float = 0.5
    macro_risk_flags: list[str] = field(default_factory=list)

    # Memory
    historical_lessons: str = ""

    # Data quality
    research_staleness_seconds: float = 9999.0
    data_quality: str = "low"  # high | medium | low

    def to_dict(self) -> dict:
        return asdict(self)


class ValidationMode(str, Enum):
    MOCK = "mock"       # Fast offline, deterministic
    CACHED = "cached"   # Uses previous real inference
    REAL = "real"       # True Ollama inference


class DataQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TimeHorizon(str, Enum):
    INTRADAY = "intraday"
    SWING = "swing"


@dataclass
class TradeDecision:
    """Full AI decision contract — the structured output from the decision engine.
    This is the machine-validated representation of one AI evaluation."""
    asset: str
    decision: Action
    confidence: int                         # 0-100
    time_horizon: TimeHorizon = TimeHorizon.INTRADAY
    thesis: str = ""                        # One-line investment thesis
    technical_basis: list[str] = field(default_factory=list)     # e.g. ["RSI oversold at 28", "MACD bullish cross"]
    news_basis: list[str] = field(default_factory=list)          # e.g. ["ETF approval rumor"]
    risk_flags: list[str] = field(default_factory=list)          # e.g. ["extreme_fear_regime"]
    inner_monologue: str = ""               # Deep reasoning / reflexion (Alpha Arena style)
    data_quality: DataQuality = DataQuality.LOW
    staleness_seconds: float = 0.0
    requires_risk_review: bool = True
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["decision"] = self.decision.value
        d["time_horizon"] = self.time_horizon.value
        d["data_quality"] = self.data_quality.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def default_hold(cls, asset: str, reason: str = "No decision available") -> TradeDecision:
        return cls(asset=asset, decision=Action.HOLD, confidence=0, thesis=reason)


@dataclass
class TradeProposal:
    """Output of the AI decision engine, input to the risk gate.
    Wraps a TradeDecision with execution context."""
    asset: str
    action: Action
    confidence: int
    reason: str
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "ai_decision_engine"
    intelligence_snapshot: Optional[dict] = None
    decision: Optional[dict] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["action"] = self.action.value
        return d

    @classmethod
    def from_decision(cls, td: TradeDecision, intel: Optional[MarketIntelligence] = None) -> TradeProposal:
        return cls(
            asset=td.asset,
            action=td.decision,
            confidence=td.confidence,
            reason=td.thesis,
            intelligence_snapshot=intel.to_dict() if intel else None,
            decision=td.to_dict(),
        )


@dataclass
class RiskAssessment:
    """Output of the risk gate layer."""
    proposal: TradeProposal
    verdict: RiskVerdict
    approved_stake: float = 0.0
    reason: str = ""
    risk_flags: list[str] = field(default_factory=list)
    portfolio_exposure_pct: float = 0.0
    daily_loss_pct: float = 0.0
    consecutive_losses: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        d["proposal"] = self.proposal.to_dict()
        return d
