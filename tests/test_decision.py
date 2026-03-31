"""
Tests for Module 3: Decision Engine and AI-to-AI Protocol.
Run: python -m pytest tests/test_decision.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.types import (
    Action, DataQuality, MarketIntelligence, TimeHorizon,
    TradeDecision, TradeProposal,
)
from ai.decision_engine import (
    _parse_response, _validate_parsed, _technical_fallback,
    _build_user_message, _assess_data_quality,
)


# ============================================================
# TEST: TradeDecision Contract
# ============================================================

class TestTradeDecision:
    def test_create_decision(self):
        td = TradeDecision(
            asset="BTC/USDC", decision=Action.BUY, confidence=75,
            thesis="RSI oversold bounce",
            technical_basis=["RSI at 28"], news_basis=["ETF rumor"],
        )
        assert td.decision == Action.BUY
        assert td.confidence == 75

    def test_serialize(self):
        td = TradeDecision(asset="ETH/USDC", decision=Action.HOLD, confidence=40)
        d = td.to_dict()
        assert d["decision"] == "hold"
        assert d["data_quality"] == "low"
        assert d["time_horizon"] == "intraday"

    def test_default_hold(self):
        td = TradeDecision.default_hold("SOL/USDC", "no signal")
        assert td.decision == Action.HOLD
        assert td.confidence == 0

    def test_to_json(self):
        td = TradeDecision(asset="BTC/USDC", decision=Action.BUY, confidence=80)
        j = json.loads(td.to_json())
        assert j["asset"] == "BTC/USDC"
        assert j["decision"] == "buy"


class TestTradeProposalFromDecision:
    def test_from_decision(self):
        td = TradeDecision(asset="BTC/USDC", decision=Action.BUY, confidence=75, thesis="test")
        intel = MarketIntelligence(asset="BTC/USDC", rsi_5m=30.0)
        tp = TradeProposal.from_decision(td, intel)
        assert tp.action == Action.BUY
        assert tp.confidence == 75
        assert tp.intelligence_snapshot is not None
        assert tp.decision is not None


# ============================================================
# TEST: Response Parser (4-stage)
# ============================================================

class TestResponseParser:
    def _intel(self, asset="BTC/USDC"):
        return MarketIntelligence(asset=asset)

    def test_valid_json(self):
        raw = '{"decision":"buy","confidence":75,"thesis":"RSI low"}'
        td = _parse_response(raw, self._intel())
        assert td.decision == Action.BUY
        assert td.confidence == 75

    def test_json_with_markdown(self):
        raw = '```json\n{"decision":"hold","confidence":30,"thesis":"uncertain"}\n```'
        td = _parse_response(raw, self._intel())
        assert td.decision == Action.HOLD

    def test_json_with_thinking(self):
        raw = '<think>hmm</think>{"decision":"buy","confidence":65,"thesis":"ok"}'
        td = _parse_response(raw, self._intel())
        assert td.decision == Action.BUY
        assert td.confidence == 65

    def test_embedded_json(self):
        raw = 'Here: {"decision":"buy","confidence":70,"thesis":"good"} done.'
        td = _parse_response(raw, self._intel())
        assert td.decision == Action.BUY

    def test_legacy_text_format(self):
        raw = "ACTION:BUY CONFIDENCE:85 REASON:Strong momentum"
        td = _parse_response(raw, self._intel())
        assert td.decision == Action.BUY
        assert td.confidence == 85

    def test_garbage_input_defaults_hold(self):
        raw = "this is complete garbage"
        td = _parse_response(raw, self._intel())
        assert td.decision == Action.HOLD
        assert td.confidence == 0

    def test_empty_input(self):
        td = _parse_response("", self._intel())
        assert td.decision == Action.HOLD

    def test_invalid_decision_normalized(self):
        raw = '{"decision":"sell","confidence":90,"thesis":"test"}'
        td = _parse_response(raw, self._intel())
        assert td.decision == Action.HOLD  # "sell" → defaults to HOLD

    def test_confidence_clamped_high(self):
        raw = '{"decision":"buy","confidence":200,"thesis":"t"}'
        td = _parse_response(raw, self._intel())
        assert td.confidence == 100

    def test_confidence_clamped_low(self):
        raw = '{"decision":"hold","confidence":-10,"thesis":"t"}'
        td = _parse_response(raw, self._intel())
        assert td.confidence == 0

    def test_arrays_parsed(self):
        raw = '{"decision":"buy","confidence":70,"thesis":"t","technical_basis":["RSI low"],"risk_flags":["fear"]}'
        td = _parse_response(raw, self._intel())
        assert "RSI low" in td.technical_basis
        assert "fear" in td.risk_flags


# ============================================================
# TEST: Validation Rules
# ============================================================

class TestValidation:
    def test_validate_parsed_normalizes(self):
        data = {"decision": "BUY", "confidence": "75", "thesis": "test \x00 chars"}
        td = _validate_parsed(data, "BTC/USDC")
        assert td.decision == Action.BUY
        assert td.confidence == 75
        assert "\x00" not in td.thesis

    def test_validate_unknown_action(self):
        data = {"decision": "short", "confidence": 50}
        td = _validate_parsed(data, "ETH/USDC")
        assert td.decision == Action.HOLD

    def test_validate_missing_confidence(self):
        data = {"decision": "buy"}
        td = _validate_parsed(data, "ETH/USDC")
        assert td.confidence == 0


# ============================================================
# TEST: Technical Fallback
# ============================================================

class TestTechnicalFallback:
    def test_oversold_bounce(self):
        intel = MarketIntelligence(asset="BTC/USDC", rsi_5m=28, macd_5m=0.1, rsi_1h=40)
        td = _technical_fallback(intel)
        assert td.decision == Action.BUY
        assert "model_unreachable" in td.risk_flags

    def test_no_signal(self):
        intel = MarketIntelligence(asset="BTC/USDC", rsi_5m=55, macd_5m=-0.1, rsi_1h=60)
        td = _technical_fallback(intel)
        assert td.decision == Action.HOLD


# ============================================================
# TEST: Data Quality Assessment
# ============================================================

class TestDataQuality:
    def test_high_quality(self):
        intel = MarketIntelligence(asset="X", research_staleness_seconds=100, news_count=5)
        assert _assess_data_quality(intel) == DataQuality.HIGH

    def test_medium_quality(self):
        intel = MarketIntelligence(asset="X", research_staleness_seconds=600, news_count=0)
        assert _assess_data_quality(intel) == DataQuality.MEDIUM

    def test_low_quality(self):
        intel = MarketIntelligence(asset="X", research_staleness_seconds=2000, news_count=0)
        assert _assess_data_quality(intel) == DataQuality.LOW


# ============================================================
# TEST: User Message Format
# ============================================================

class TestUserMessage:
    def test_structured_format(self):
        intel = MarketIntelligence(
            asset="BTC/USDC", rsi_5m=35.0, macd_5m=-0.01,
            close_price=85000.0, market_regime="extreme_fear",
            macro_risk_flags=["extreme_fear_regime"],
        )
        msg = _build_user_message(intel)
        assert "BTC/USDC" in msg
        assert "85000.00" in msg
        assert "extreme_fear" in msg
        assert "RISK_FLAGS" in msg
        assert "JSON" in msg

    def test_no_prose(self):
        intel = MarketIntelligence(asset="ETH/USDC")
        msg = _build_user_message(intel)
        # Should not contain conversational language
        for word in ["please", "would you", "could you", "I think"]:
            assert word.lower() not in msg.lower()
