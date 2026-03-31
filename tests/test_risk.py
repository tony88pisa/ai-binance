"""
Tests for Module 4: Risk Gate.
Run: python -m pytest tests/test_risk.py -v
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.types import Action, DataQuality, RiskVerdict, TradeDecision, TradeProposal
from config.settings import RiskSettings, Settings
from risk.gate import evaluate_proposal


@pytest.fixture
def mock_settings():
    with patch("risk.gate.get_settings") as mock_get:
        settings = Settings(risk=RiskSettings(
            max_open_trades=3,
            max_stake_pct=0.33,
            max_stake_abs=20.0,
            max_consecutive_losses=3
        ))
        mock_get.return_value = settings
        yield settings


def make_proposal(decision: Action, confidence: int = 85, data_quality: DataQuality = DataQuality.HIGH, macro_risk: float = 0.5):
    td = TradeDecision(
        asset="BTC/USDC",
        decision=decision,
        confidence=confidence,
        data_quality=data_quality
    )
    return TradeProposal.from_decision(
        td,
        intel=None  # We'll mock the dict if needed
    )


def test_hold_is_always_approved(mock_settings):
    proposal = make_proposal(Action.HOLD)
    res = evaluate_proposal(proposal, current_wallet_balance=100.0, open_trades_count=0)
    assert res.verdict == RiskVerdict.APPROVED
    assert res.approved_stake == 0.0


def test_circuit_breaker_consecutive_losses(mock_settings):
    proposal = make_proposal(Action.BUY)
    res = evaluate_proposal(
        proposal, current_wallet_balance=100.0, open_trades_count=0, consecutive_losses=3
    )
    assert res.verdict == RiskVerdict.BLOCKED
    assert "circuit_breaker_active" in res.risk_flags


def test_max_open_trades_block(mock_settings):
    proposal = make_proposal(Action.BUY)
    res = evaluate_proposal(
        proposal, current_wallet_balance=100.0, open_trades_count=3
    )
    assert res.verdict == RiskVerdict.BLOCKED
    assert "max_trades_reached" in res.risk_flags


def test_low_data_quality_block(mock_settings):
    # Low quality data requires at least 80 confidence to trade.
    proposal = make_proposal(Action.BUY, confidence=75, data_quality=DataQuality.LOW)
    res = evaluate_proposal(proposal, current_wallet_balance=100.0, open_trades_count=0)
    assert res.verdict == RiskVerdict.BLOCKED
    assert "low_data_quality_block" in res.risk_flags


def test_low_data_quality_approved_if_high_confidence(mock_settings):
    # Confidence >= 80 overrides the low data quality block
    proposal = make_proposal(Action.BUY, confidence=85, data_quality=DataQuality.LOW)
    res = evaluate_proposal(proposal, current_wallet_balance=100.0, open_trades_count=0)
    assert res.verdict == RiskVerdict.APPROVED
    assert res.approved_stake > 0


def test_stake_sizing_relative_cap(mock_settings):
    # Wallet=30, cap=33% -> max stake 9.9
    proposal = make_proposal(Action.BUY, confidence=90, data_quality=DataQuality.HIGH)
    res = evaluate_proposal(proposal, current_wallet_balance=30.0, open_trades_count=0)
    assert res.verdict == RiskVerdict.APPROVED
    assert res.approved_stake == 9.9


def test_stake_sizing_absolute_cap(mock_settings):
    # Wallet=1000, cap=33% (=330), but hard cap is 20
    proposal = make_proposal(Action.BUY, confidence=90, data_quality=DataQuality.HIGH)
    res = evaluate_proposal(proposal, current_wallet_balance=1000.0, open_trades_count=0)
    assert res.verdict == RiskVerdict.APPROVED
    assert res.approved_stake == 20.0


def test_penalty_consecutive_losses(mock_settings):
    # Wallet=60, relative max=19.8. One loss -> 15% penalty -> 19.8 * 0.85 = 16.83
    proposal = make_proposal(Action.BUY, confidence=90, data_quality=DataQuality.HIGH)
    res = evaluate_proposal(proposal, current_wallet_balance=60.0, open_trades_count=0, consecutive_losses=1)
    assert res.verdict == RiskVerdict.REDUCED
    assert res.approved_stake == 16.83
    assert "consecutive_loss_penalty_1" in res.risk_flags


def test_stake_too_small_block(mock_settings):
    # Wallet=10 -> relative max 3.3. 
    # Two losses -> 30% penalty.
    # Medium data + conf 75 -> 25% penalty.
    # Total penalty 55%. Max 3.3 * 0.45 = 1.485. 
    # Under minimum 2.0 -> BLOCKED.
    proposal = make_proposal(Action.BUY, confidence=75, data_quality=DataQuality.MEDIUM)
    res = evaluate_proposal(proposal, current_wallet_balance=10.0, open_trades_count=0, consecutive_losses=2)
    assert res.verdict == RiskVerdict.BLOCKED
    assert res.approved_stake == 0.0
    assert "stake_too_small" in res.risk_flags
