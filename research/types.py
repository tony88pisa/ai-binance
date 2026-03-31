"""
Research data schemas — structured types for the always-on research pipeline.

These types are produced by the research daemon and consumed by the decision engine.
They are never passed through LLM prompts — they are machine-state records.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SentimentLabel(str, Enum):
    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


class MarketRegime(str, Enum):
    EXTREME_FEAR = "extreme_fear"
    FEAR = "fear"
    NEUTRAL = "neutral"
    GREED = "greed"
    EXTREME_GREED = "extreme_greed"
    UNKNOWN = "unknown"


class Freshness(str, Enum):
    LIVE = "live"          # < 15 min
    RECENT = "recent"      # < 1 hour
    AGING = "aging"        # < 4 hours
    STALE = "stale"        # > 4 hours


@dataclass
class RawNewsItem:
    """Raw item straight from the feed — before any processing."""
    source: str
    title: str
    url: str
    published_at: str = ""
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary_raw: str = ""

    def dedupe_hash(self) -> str:
        key = f"{self.source}:{self.title.lower().strip()}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass
class NormalizedNewsItem:
    """Processed news item with sentiment and asset tagging."""
    source: str
    title: str
    url: str
    published_at: str
    discovered_at: str
    dedupe_hash: str

    # Tagging
    asset_tags: list[str] = field(default_factory=list)     # ["BTC", "ETH"]
    themes: list[str] = field(default_factory=list)          # ["regulation", "etf"]

    # Scoring
    sentiment_label: SentimentLabel = SentimentLabel.NEUTRAL
    sentiment_score: float = 0.0   # -1.0 to +1.0
    urgency_score: float = 0.0     # 0.0 to 1.0
    relevance_score: float = 0.0   # 0.0 to 1.0

    # Summaries
    summary_short: str = ""

    # Lifecycle
    expiry_hours: float = 6.0
    freshness: Freshness = Freshness.LIVE

    def is_expired(self) -> bool:
        try:
            disc = datetime.fromisoformat(self.discovered_at)
            age_hours = (datetime.now(timezone.utc) - disc).total_seconds() / 3600
            return age_hours > self.expiry_hours
        except Exception:
            return True

    def compute_freshness(self) -> Freshness:
        try:
            disc = datetime.fromisoformat(self.discovered_at)
            age_min = (datetime.now(timezone.utc) - disc).total_seconds() / 60
            if age_min < 15:
                return Freshness.LIVE
            elif age_min < 60:
                return Freshness.RECENT
            elif age_min < 240:
                return Freshness.AGING
            return Freshness.STALE
        except Exception:
            return Freshness.STALE

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sentiment_label"] = self.sentiment_label.value
        d["freshness"] = self.compute_freshness().value
        return d


@dataclass
class AssetResearchSnapshot:
    """Per-asset intelligence summary — consumed by the decision engine."""
    asset: str
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Aggregated sentiment
    news_count: int = 0
    avg_sentiment_score: float = 0.0
    dominant_sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    top_themes: list[str] = field(default_factory=list)
    top_headlines: list[str] = field(default_factory=list)  # max 3

    # Urgency
    max_urgency: float = 0.0

    # Freshness
    freshest_item_age_min: float = 999.0
    data_freshness: Freshness = Freshness.STALE

    def to_dict(self) -> dict:
        d = asdict(self)
        d["dominant_sentiment"] = self.dominant_sentiment.value
        d["data_freshness"] = self.data_freshness.value
        return d


@dataclass
class MarketRegimeSnapshot:
    """Global market regime from Fear & Greed Index."""
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fear_greed_value: int = 50
    fear_greed_label: str = "Neutral"
    regime: MarketRegime = MarketRegime.NEUTRAL

    @staticmethod
    def from_fng(value: int, label: str) -> MarketRegimeSnapshot:
        if value <= 20:
            regime = MarketRegime.EXTREME_FEAR
        elif value <= 40:
            regime = MarketRegime.FEAR
        elif value <= 60:
            regime = MarketRegime.NEUTRAL
        elif value <= 80:
            regime = MarketRegime.GREED
        else:
            regime = MarketRegime.EXTREME_GREED
        return MarketRegimeSnapshot(
            fear_greed_value=value, fear_greed_label=label, regime=regime
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["regime"] = self.regime.value
        return d


@dataclass
class MacroRiskSnapshot:
    """Top-level risk assessment from research signals."""
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    regime: MarketRegime = MarketRegime.NEUTRAL
    overall_sentiment: SentimentLabel = SentimentLabel.NEUTRAL
    risk_level: float = 0.5       # 0.0 (safe) to 1.0 (extreme risk)
    risk_flags: list[str] = field(default_factory=list)
    recommendation: str = "normal_trading"  # conservative | normal_trading | aggressive_caution

    def to_dict(self) -> dict:
        d = asdict(self)
        d["regime"] = self.regime.value
        d["overall_sentiment"] = self.overall_sentiment.value
        return d


@dataclass
class ResearchState:
    """Complete research state — written atomically by the daemon."""
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    cycle_count: int = 0
    news_items: list[dict] = field(default_factory=list)
    asset_snapshots: dict[str, dict] = field(default_factory=dict)
    market_regime: dict = field(default_factory=dict)
    macro_risk: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)
