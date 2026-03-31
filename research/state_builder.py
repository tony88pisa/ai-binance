"""
Research state builder — aggregates normalized news into per-asset and macro snapshots.

Takes individual NormalizedNewsItems and produces:
- AssetResearchSnapshot (per asset)
- MacroRiskSnapshot (overall market assessment)
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone

from research.types import (
    AssetResearchSnapshot, Freshness, MacroRiskSnapshot,
    MarketRegimeSnapshot, MarketRegime, NormalizedNewsItem, SentimentLabel,
)

logger = logging.getLogger(__name__)

TRACKED_ASSETS = ["BTC", "ETH", "SOL"]


def build_asset_snapshots(
    news_items: list[NormalizedNewsItem],
) -> dict[str, AssetResearchSnapshot]:
    """Build per-asset research summaries from normalized news."""
    # Group news by asset
    asset_news: dict[str, list[NormalizedNewsItem]] = defaultdict(list)
    for item in news_items:
        if item.is_expired():
            continue
        for tag in item.asset_tags:
            if tag in TRACKED_ASSETS:
                asset_news[tag].append(item)
        # CRYPTO tag contributes to all
        if "CRYPTO" in item.asset_tags:
            for asset in TRACKED_ASSETS:
                if asset not in item.asset_tags:
                    asset_news[asset].append(item)

    snapshots: dict[str, AssetResearchSnapshot] = {}

    for asset in TRACKED_ASSETS:
        items = asset_news.get(asset, [])

        if not items:
            snapshots[asset] = AssetResearchSnapshot(
                asset=asset, news_count=0,
                data_freshness=Freshness.STALE,
            )
            continue

        # Aggregate sentiment
        scores = [it.sentiment_score for it in items]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Dominant sentiment
        labels = [it.sentiment_label for it in items]
        label_counts = Counter(labels)
        dominant = label_counts.most_common(1)[0][0] if label_counts else SentimentLabel.NEUTRAL

        # Top themes
        all_themes: list[str] = []
        for it in items:
            all_themes.extend(it.themes)
        theme_counts = Counter(all_themes)
        top_themes = [t for t, _ in theme_counts.most_common(3)]

        # Top headlines (by relevance)
        sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=True)
        top_headlines = [it.title[:80] for it in sorted_items[:3]]

        # Max urgency
        max_urgency = max((it.urgency_score for it in items), default=0.0)

        # Freshness
        now = datetime.now(timezone.utc)
        freshest_age = 999.0
        for it in items:
            try:
                disc = datetime.fromisoformat(it.discovered_at)
                age = (now - disc).total_seconds() / 60
                freshest_age = min(freshest_age, age)
            except Exception:
                pass

        if freshest_age < 15:
            data_freshness = Freshness.LIVE
        elif freshest_age < 60:
            data_freshness = Freshness.RECENT
        elif freshest_age < 240:
            data_freshness = Freshness.AGING
        else:
            data_freshness = Freshness.STALE

        snapshots[asset] = AssetResearchSnapshot(
            asset=asset,
            news_count=len(items),
            avg_sentiment_score=round(avg_score, 3),
            dominant_sentiment=dominant,
            top_themes=top_themes,
            top_headlines=top_headlines,
            max_urgency=round(max_urgency, 3),
            freshest_item_age_min=round(freshest_age, 1),
            data_freshness=data_freshness,
        )

    return snapshots


def build_macro_risk(
    asset_snapshots: dict[str, AssetResearchSnapshot],
    regime: MarketRegimeSnapshot,
) -> MacroRiskSnapshot:
    """Build overall macro risk assessment from asset snapshots + market regime."""
    risk_flags: list[str] = []
    risk_level = 0.5  # baseline

    # Factor 1: Fear & Greed
    if regime.regime == MarketRegime.EXTREME_FEAR:
        risk_level += 0.2
        risk_flags.append("extreme_fear_regime")
    elif regime.regime == MarketRegime.FEAR:
        risk_level += 0.1
        risk_flags.append("fear_regime")
    elif regime.regime == MarketRegime.EXTREME_GREED:
        risk_level += 0.15
        risk_flags.append("extreme_greed_bubble_risk")

    # Factor 2: Aggregate sentiment across all assets
    all_scores = [s.avg_sentiment_score for s in asset_snapshots.values() if s.news_count > 0]
    if all_scores:
        avg_market_sentiment = sum(all_scores) / len(all_scores)
        if avg_market_sentiment < -0.3:
            risk_level += 0.15
            risk_flags.append("negative_news_dominance")
        elif avg_market_sentiment > 0.3:
            risk_level -= 0.1  # positive news reduces risk

    # Factor 3: Urgency signals
    max_urgency = max((s.max_urgency for s in asset_snapshots.values()), default=0.0)
    if max_urgency > 0.7:
        risk_level += 0.1
        risk_flags.append("high_urgency_news")

    # Factor 4: Data staleness
    all_stale = all(s.data_freshness == Freshness.STALE for s in asset_snapshots.values())
    if all_stale:
        risk_flags.append("all_data_stale")

    risk_level = max(0.0, min(1.0, risk_level))

    # Overall sentiment
    if all_scores:
        avg = sum(all_scores) / len(all_scores)
        if avg >= 0.15:
            overall = SentimentLabel.BULLISH
        elif avg <= -0.15:
            overall = SentimentLabel.BEARISH
        else:
            overall = SentimentLabel.NEUTRAL
    else:
        overall = SentimentLabel.NEUTRAL

    # Recommendation
    if risk_level > 0.7:
        recommendation = "conservative"
    elif risk_level < 0.3:
        recommendation = "normal_trading"
    else:
        recommendation = "normal_trading"

    return MacroRiskSnapshot(
        regime=regime.regime,
        overall_sentiment=overall,
        risk_level=round(risk_level, 3),
        risk_flags=risk_flags,
        recommendation=recommendation,
    )
