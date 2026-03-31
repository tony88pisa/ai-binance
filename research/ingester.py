"""
News ingestion pipeline — fetches, normalizes, deduplicates, and scores news.

No LLM calls. Pure keyword-based sentiment and tagging.
Designed to be called by the research daemon on a schedule.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import feedparser
import requests

from config.settings import get_settings
from research.types import (
    Freshness, MarketRegime, MarketRegimeSnapshot,
    NormalizedNewsItem, RawNewsItem, SentimentLabel,
)

logger = logging.getLogger(__name__)

# === KEYWORD DICTIONARIES ===

BULLISH_KEYWORDS = {
    "rally": 0.4, "surge": 0.5, "breakout": 0.4, "bullish": 0.6,
    "pump": 0.3, "ath": 0.5, "all-time high": 0.5, "adoption": 0.4,
    "institutional": 0.3, "etf approved": 0.7, "etf": 0.3, "partnership": 0.3,
    "upgrade": 0.2, "accumulation": 0.3, "recovery": 0.3, "growth": 0.2,
    "buy": 0.2, "inflow": 0.3, "positive": 0.2, "gain": 0.3,
}

BEARISH_KEYWORDS = {
    "crash": -0.6, "dump": -0.5, "fear": -0.3, "bearish": -0.6,
    "hack": -0.7, "exploit": -0.6, "regulation": -0.3, "ban": -0.5,
    "lawsuit": -0.5, "sec": -0.3, "fraud": -0.6, "scam": -0.5,
    "sell-off": -0.5, "selloff": -0.5, "liquidation": -0.4, "plunge": -0.5,
    "outflow": -0.3, "negative": -0.2, "loss": -0.3, "decline": -0.3,
    "collapse": -0.7, "bankruptcy": -0.7, "insolvency": -0.6,
}

URGENCY_KEYWORDS = {
    "breaking": 0.9, "urgent": 0.8, "alert": 0.7, "just in": 0.8,
    "flash": 0.7, "emergency": 0.9, "crash": 0.8, "hack": 0.9,
    "exploit": 0.8, "breaking news": 0.9,
}

ASSET_PATTERNS = {
    "BTC": [r"\bbitcoin\b", r"\bbtc\b"],
    "ETH": [r"\bethereum\b", r"\beth\b"],
    "SOL": [r"\bsolana\b", r"\bsol\b"],
    "CRYPTO": [r"\bcrypto\b", r"\bcryptocurrency\b", r"\bdefi\b", r"\bweb3\b"],
}

THEME_PATTERNS = {
    "regulation": [r"\bregulat", r"\bsec\b", r"\bcftc\b", r"\blegal", r"\blawsuit"],
    "etf": [r"\betf\b"],
    "hack": [r"\bhack", r"\bexploit", r"\bbreach"],
    "adoption": [r"\badopt", r"\binstitution", r"\bpartner"],
    "price_action": [r"\brally", r"\bcrash", r"\bsurge", r"\bdump", r"\bpump"],
    "macro": [r"\bfed\b", r"\binflation", r"\binterest rate", r"\bgdp\b"],
}


def fetch_raw_news() -> list[RawNewsItem]:
    """Fetch news from all configured RSS feeds. Never crashes."""
    settings = get_settings()
    items: list[RawNewsItem] = []

    for name, url in settings.news.feeds.items():
        try:
            resp = requests.get(url, timeout=settings.news.feed_timeout)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            for entry in feed.entries[:5]:  # Max 5 per source
                pub_date = ""
                if hasattr(entry, "published"):
                    pub_date = entry.published
                items.append(RawNewsItem(
                    source=name,
                    title=_sanitize(entry.get("title", "")),
                    url=entry.get("link", ""),
                    published_at=pub_date,
                    summary_raw=_sanitize(entry.get("summary", ""))[:200],
                ))
            logger.debug(f"Feed {name}: {len(feed.entries)} entries fetched")
        except requests.exceptions.Timeout:
            logger.debug(f"Feed {name}: timeout after {settings.news.feed_timeout}s")
        except Exception as e:
            logger.debug(f"Feed {name}: error {e}")

    return items


def fetch_fear_and_greed() -> MarketRegimeSnapshot:
    """Fetch Fear & Greed Index. Returns UNKNOWN on failure."""
    settings = get_settings()
    try:
        resp = requests.get(settings.news.fng_url, timeout=settings.news.fng_timeout)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if data:
            value = int(data[0].get("value", 50))
            label = data[0].get("value_classification", "Neutral")
            return MarketRegimeSnapshot.from_fng(value, label)
    except Exception as e:
        logger.debug(f"Fear & Greed fetch failed: {e}")

    return MarketRegimeSnapshot(regime=MarketRegime.UNKNOWN)


def normalize_news(raw_items: list[RawNewsItem],
                   seen_hashes: set[str]) -> list[NormalizedNewsItem]:
    """Normalize, deduplicate, tag, and score raw news items."""
    normalized: list[NormalizedNewsItem] = []

    for raw in raw_items:
        dhash = raw.dedupe_hash()

        # Deduplicate
        if dhash in seen_hashes:
            continue
        seen_hashes.add(dhash)

        text = f"{raw.title} {raw.summary_raw}".lower()

        # Sentiment scoring
        sentiment_score = _compute_sentiment(text)
        sentiment_label = _score_to_label(sentiment_score)

        # Asset tagging
        asset_tags = _tag_assets(text)

        # Theme tagging
        themes = _tag_themes(text)

        # Urgency scoring
        urgency = _compute_urgency(text)

        # Relevance: higher if mentions our tracked assets
        relevance = min(1.0, 0.3 + 0.2 * len(asset_tags) + urgency * 0.3)

        item = NormalizedNewsItem(
            source=raw.source,
            title=raw.title,
            url=raw.url,
            published_at=raw.published_at,
            discovered_at=raw.discovered_at,
            dedupe_hash=dhash,
            asset_tags=asset_tags,
            themes=themes,
            sentiment_label=sentiment_label,
            sentiment_score=round(sentiment_score, 3),
            urgency_score=round(urgency, 3),
            relevance_score=round(relevance, 3),
            summary_short=raw.title[:100],
        )
        item.freshness = item.compute_freshness()
        normalized.append(item)

    return normalized


def _compute_sentiment(text: str) -> float:
    """Keyword-based sentiment scoring. Returns -1.0 to +1.0."""
    score = 0.0
    for kw, weight in BULLISH_KEYWORDS.items():
        if kw in text:
            score += weight
    for kw, weight in BEARISH_KEYWORDS.items():
        if kw in text:
            score += weight  # weight is already negative
    return max(-1.0, min(1.0, score))


def _score_to_label(score: float) -> SentimentLabel:
    if score >= 0.5:
        return SentimentLabel.VERY_BULLISH
    elif score >= 0.15:
        return SentimentLabel.BULLISH
    elif score <= -0.5:
        return SentimentLabel.VERY_BEARISH
    elif score <= -0.15:
        return SentimentLabel.BEARISH
    return SentimentLabel.NEUTRAL


def _tag_assets(text: str) -> list[str]:
    tags = []
    for asset, patterns in ASSET_PATTERNS.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            tags.append(asset)
    return tags


def _tag_themes(text: str) -> list[str]:
    tags = []
    for theme, patterns in THEME_PATTERNS.items():
        if any(re.search(p, text, re.IGNORECASE) for p in patterns):
            tags.append(theme)
    return tags


def _compute_urgency(text: str) -> float:
    max_urg = 0.0
    for kw, score in URGENCY_KEYWORDS.items():
        if kw in text:
            max_urg = max(max_urg, score)
    return max_urg


def _sanitize(text: str) -> str:
    """Strip HTML tags and force ASCII-safe."""
    text = re.sub(r"<[^>]+>", "", text)
    return text.encode("ascii", errors="replace").decode("ascii").strip()
