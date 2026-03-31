"""
Integration testing for Module 6.

Validates the complete execution flow from Research -> Decision -> Risk.
Validates Degraded Modes (No Internet, Invalid JSON).
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.decision_engine import evaluate
from ai.types import Action, DataQuality, MarketIntelligence, TradeDecision, ValidationMode
from config.settings import ModelSettings, Settings
from risk.gate import evaluate_proposal
from ai.types import TradeProposal, RiskVerdict


@pytest.fixture
def base_intel():
    return MarketIntelligence(
        asset="BTC/USDC",
        rsi_5m=25.0,
        macd_5m=0.005,
        rsi_1h=40.0,
        close_price=60000.0,
        fear_and_greed_value=25,
        market_regime="fear",
        news_sentiment_score=0.1,
        news_count=5,
        macro_risk_level=0.4,
        research_staleness_seconds=120,
    )


def test_full_pipeline_mock_mode(base_intel):
    """Test full pipeline: Decision (Mock) -> Proposal -> Risk Gate."""
    with patch("ai.decision_engine.get_settings") as mock_set:
        mock_set.return_value = Settings(model=ModelSettings(validation_mode="mock"))
        
        # 1. AI evaluation (should trigger Mock deterministic logic)
        decision = evaluate(base_intel)
        
        # MOCK logic says: RSI < 30 and MACD > 0 -> BUY conf 85
        assert decision.decision == Action.BUY
        assert decision.confidence == 85
        assert "mock_mode_active" in decision.risk_flags
        
        # 2. Risk Evaluation
        proposal = TradeProposal.from_decision(decision, intel=base_intel)
        risk_res = evaluate_proposal(
            proposal,
            current_wallet_balance=100.0,
            open_trades_count=0
        )
        
        # 3. Validation
        assert risk_res.verdict == RiskVerdict.APPROVED
        assert risk_res.approved_stake > 0


def test_degraded_mode_model_timeout(base_intel):
    """Test pipeline resilience when Ollama is offline."""
    with patch("ai.decision_engine.get_settings") as mock_set:
        mock_set.return_value = Settings(model=ModelSettings(validation_mode="real", max_retries=1))
        
        with patch("ai.decision_engine.requests.post") as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
            
            # 1. AI evaluation (should use technical fallback)
            decision = evaluate(base_intel)
            
            # Technical fallback says: RSI 5m < 35, MACD > 0, RSI 1h < 45 -> BUY conf 50
            assert decision.decision == Action.BUY
            assert decision.confidence == 50
            assert decision.data_quality == DataQuality.LOW
            assert "model_unreachable" in decision.risk_flags
            
            # 2. Risk Gate should BLOCK it because DataQuality is LOW and Confidence < 80
            proposal = TradeProposal.from_decision(decision, intel=base_intel)
            risk_res = evaluate_proposal(
                proposal,
                current_wallet_balance=100.0,
                open_trades_count=0
            )
            
            assert risk_res.verdict == RiskVerdict.BLOCKED
            assert "low_data_quality_block" in risk_res.risk_flags


def test_cached_mode_behavior(base_intel, tmp_path):
    """Test inference caching functionality."""
    cache_file = tmp_path / "test_cache.json"
    
    with patch("ai.cache.get_settings") as mock_cache_set, \
         patch("ai.decision_engine.get_settings") as mock_decision_set:
         
        from config.settings import PathSettings
        settings = Settings(
            model=ModelSettings(validation_mode="cached"),
            paths=PathSettings(inference_cache_file=cache_file)
        )
        mock_cache_set.return_value = settings
        mock_decision_set.return_value = settings
        
        # 1. Cache is empty, should fall back to REAL inference 
        with patch("ai.decision_engine._call_model", return_value='{"action":"BUY","confidence":95,"reason":"test"}'):
            decision1 = evaluate(base_intel)
            assert decision1.confidence == 95
            
        # Cache file should now exist
        assert cache_file.exists()
        
        # 2. Call again, should HIT cache without calling model
        with patch("ai.decision_engine._call_model") as mock_call:
            decision2 = evaluate(base_intel)
            assert decision2.confidence == 95
            assert decision2.decision == Action.BUY
            mock_call.assert_not_called()

def test_cache_key_material_difference(base_intel):
    """Test that materially different contexts yield different cache hashes."""
    from ai.cache import _generate_context_hash
    hash1 = _generate_context_hash(base_intel)
    
    # Change something immaterial (should hash different because price rounded differently? Actually close_price is rounded to 2).
    # Let's change something material like RSI
    intel2 = MarketIntelligence(**base_intel.to_dict())
    intel2.rsi_5m = 90.0
    hash2 = _generate_context_hash(intel2)
    assert hash1 != hash2, "Material difference in RSI should change cache hash"

def test_validation_mode_live_mock_startup():
    """Verify that validate_and_report physically returns False when MOCK + LIVE is attempted."""
    import os
    from config.validator import validate_config, Severity
    with patch("config.validator.json.load") as mock_json:
        # Mocking config.json as live
        mock_json.return_value = {"dry_run": False}
        
        os.environ["VALIDATION_MODE"] = "mock"
        try:
            from pathlib import Path
            with patch("pathlib.Path.exists", return_value=True), \
                 patch("builtins.open"):
                issues = validate_config(Path("dummy.json"))
                
                criticals = [i for i in issues if i.severity == Severity.CRITICAL and "mock" in i.message.lower()]
                assert len(criticals) > 0, "Should raise CRITICAL issue when mock + live"
        finally:
            os.environ.pop("VALIDATION_MODE")
