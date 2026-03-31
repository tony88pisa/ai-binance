"""
Tests for Module 2: Research Pipeline.
Run: python -m pytest tests/test_research.py -v
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.types import (
    Freshness, MarketRegime, MarketRegimeSnapshot, NormalizedNewsItem,
    RawNewsItem, ResearchState, SentimentLabel, AssetResearchSnapshot,
    MacroRiskSnapshot,
)
from research.ingester import (
    normalize_news, _compute_sentiment, _score_to_label,
    _tag_assets, _tag_themes, _compute_urgency,
)
from research.state_builder import build_asset_snapshots, build_macro_risk
from research.store import write_state, read_state


# ============================================================
# TEST: Raw News Item
# ============================================================

class TestRawNewsItem:
    def test_dedupe_hash_deterministic(self):
        item = RawNewsItem(source="test", title="Bitcoin rallies to 100k", url="http://test.com")
        h1 = item.dedupe_hash()
        h2 = item.dedupe_hash()
        assert h1 == h2
        assert len(h1) == 16

    def test_dedupe_hash_case_insensitive(self):
        item1 = RawNewsItem(source="test", title="Bitcoin Rallies", url="")
        item2 = RawNewsItem(source="test", title="bitcoin rallies", url="")
        assert item1.dedupe_hash() == item2.dedupe_hash()

    def test_different_sources_different_hash(self):
        item1 = RawNewsItem(source="cointelegraph", title="Same Title", url="")
        item2 = RawNewsItem(source="coindesk", title="Same Title", url="")
        assert item1.dedupe_hash() != item2.dedupe_hash()


# ============================================================
# TEST: Sentiment Scoring
# ============================================================

class TestSentiment:
    def test_bullish_keywords(self):
        score = _compute_sentiment("bitcoin rally surge ath breakout")
        assert score > 0.3

    def test_bearish_keywords(self):
        score = _compute_sentiment("crypto crash dump fear liquidation")
        assert score < -0.3

    def test_neutral_text(self):
        score = _compute_sentiment("quarterly report released by company")
        assert -0.15 <= score <= 0.15

    def test_score_clamped(self):
        score = _compute_sentiment("rally surge ath breakout pump bullish etf approved")
        assert score <= 1.0

    def test_label_very_bullish(self):
        assert _score_to_label(0.6) == SentimentLabel.VERY_BULLISH

    def test_label_bearish(self):
        assert _score_to_label(-0.3) == SentimentLabel.BEARISH

    def test_label_neutral(self):
        assert _score_to_label(0.0) == SentimentLabel.NEUTRAL


# ============================================================
# TEST: Asset Tagging
# ============================================================

class TestAssetTagging:
    def test_btc_detected(self):
        tags = _tag_assets("bitcoin price hits new ath")
        assert "BTC" in tags

    def test_eth_detected(self):
        tags = _tag_assets("ethereum upgrade scheduled")
        assert "ETH" in tags

    def test_sol_detected(self):
        tags = _tag_assets("solana network outage")
        assert "SOL" in tags

    def test_multiple_assets(self):
        tags = _tag_assets("btc and eth rally together")
        assert "BTC" in tags
        assert "ETH" in tags

    def test_no_match(self):
        tags = _tag_assets("stock market news today")
        assert tags == []


# ============================================================
# TEST: Theme Tagging
# ============================================================

class TestThemeTagging:
    def test_regulation(self):
        themes = _tag_themes("sec files lawsuit against crypto exchange")
        assert "regulation" in themes

    def test_hack(self):
        themes = _tag_themes("major defi protocol hacked for 100m")
        assert "hack" in themes

    def test_etf(self):
        themes = _tag_themes("bitcoin spot etf approved by regulators")
        assert "etf" in themes


# ============================================================
# TEST: Urgency
# ============================================================

class TestUrgency:
    def test_breaking_news(self):
        score = _compute_urgency("breaking: major exchange halt")
        assert score >= 0.8

    def test_normal_news(self):
        score = _compute_urgency("quarterly report shows growth")
        assert score == 0.0


# ============================================================
# TEST: Normalization & Dedup
# ============================================================

class TestNormalization:
    def test_dedup_removes_duplicates(self):
        items = [
            RawNewsItem(source="test", title="BTC rallies", url="a"),
            RawNewsItem(source="test", title="BTC rallies", url="b"),
        ]
        result = normalize_news(items, set())
        assert len(result) == 1

    def test_different_titles_kept(self):
        items = [
            RawNewsItem(source="test", title="BTC rallies", url="a"),
            RawNewsItem(source="test", title="ETH drops", url="b"),
        ]
        result = normalize_news(items, set())
        assert len(result) == 2


# ============================================================
# TEST: State Builder
# ============================================================

class TestStateBuilder:
    def _make_item(self, title, asset_tags, sentiment=0.0):
        return NormalizedNewsItem(
            source="test", title=title, url="", published_at="",
            discovered_at="2099-01-01T00:00:00+00:00",
            dedupe_hash="h" + title[:8],
            asset_tags=asset_tags, sentiment_score=sentiment,
            sentiment_label=SentimentLabel.NEUTRAL,
        )

    def test_builds_all_assets(self):
        items = [self._make_item("BTC up", ["BTC"], 0.3)]
        snapshots = build_asset_snapshots(items)
        assert "BTC" in snapshots
        assert "ETH" in snapshots
        assert "SOL" in snapshots

    def test_btc_snapshot_populated(self):
        items = [
            self._make_item("BTC rally", ["BTC"], 0.5),
            self._make_item("BTC surge", ["BTC"], 0.3),
        ]
        snapshots = build_asset_snapshots(items)
        assert snapshots["BTC"].news_count == 2
        assert snapshots["BTC"].avg_sentiment_score > 0


class TestMacroRisk:
    def test_extreme_fear_increases_risk(self):
        regime = MarketRegimeSnapshot.from_fng(10, "Extreme Fear")
        snapshots = {"BTC": AssetResearchSnapshot(asset="BTC")}
        risk = build_macro_risk(snapshots, regime)
        assert risk.risk_level > 0.6
        assert "extreme_fear_regime" in risk.risk_flags


# ============================================================
# TEST: Store (Atomic Read/Write)
# ============================================================

class TestStore:
    def test_write_and_read(self, tmp_path):
        path = tmp_path / "state.json"
        state = ResearchState(cycle_count=5)
        assert write_state(state, path)
        loaded = read_state(path)
        assert loaded is not None
        assert loaded.cycle_count == 5

    def test_read_missing_file(self, tmp_path):
        result = read_state(tmp_path / "missing.json")
        assert result is None
