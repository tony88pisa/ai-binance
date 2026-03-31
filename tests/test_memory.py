"""
Tests for Module 5: Memory, Evaluation, and Honest Learning.
Run: python -m pytest tests/test_memory.py -v
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.types import (
    DecisionRecord, EvaluationSummary, EventRecord, MemoryStore, OutcomeRecord
)
from memory.manager import MemoryManager


@pytest.fixture
def mem_mgr(tmp_path):
    # Use temporary file for isolated tests
    db_path = tmp_path / "test_memory.json"
    return MemoryManager(path=db_path)


# ============================================================
# TEST: Layer 1 - Event Logging
# ============================================================

def test_log_event(mem_mgr):
    mem_mgr.log_event("startup", "Bot started", version="2026.2")
    assert len(mem_mgr._store.events) == 1
    ev = mem_mgr._store.events[0]
    assert ev["event_type"] == "startup"
    assert ev["message"] == "Bot started"
    assert ev["data"]["version"] == "2026.2"


# ============================================================
# TEST: Layer 2 - Decision Logging
# ============================================================

def test_log_decision(mem_mgr):
    dec_id = mem_mgr.generate_decision_id()
    assert dec_id.startswith("D-")
    
    record = DecisionRecord(
        id=dec_id,
        timestamp_utc="2099-01-01T00:00:00Z",
        asset="BTC/USDC",
        action="buy",
        confidence=85,
        thesis="Oversold"
    )
    res_id = mem_mgr.log_decision(record)
    assert res_id == dec_id
    
    assert len(mem_mgr._store.decisions) == 1
    d = mem_mgr._store.decisions[0]
    assert d["asset"] == "BTC/USDC"
    assert d["confidence"] == 85


# ============================================================
# TEST: Layer 3 - Outcome Logging
# ============================================================

def test_log_outcome(mem_mgr):
    outcome = OutcomeRecord(
        decision_id="D-123",
        asset="BTC/USDC",
        realized_pnl_pct=5.5,
        was_profitable=True
    )
    mem_mgr.log_outcome(outcome)
    
    assert len(mem_mgr._store.outcomes) == 1
    o = mem_mgr._store.outcomes[0]
    assert o["realized_pnl_pct"] == 5.5
    assert o["was_profitable"] is True


# ============================================================
# TEST: Layer 4 - Retrieval
# ============================================================

def test_retrieval_filtering(mem_mgr):
    # Setup data
    mem_mgr.log_outcome(OutcomeRecord(decision_id="1", asset="BTC/USDC", market_regime_at_exit="fear"))
    mem_mgr.log_outcome(OutcomeRecord(decision_id="2", asset="ETH/USDC", market_regime_at_exit="greed"))
    mem_mgr.log_outcome(OutcomeRecord(decision_id="3", asset="BTC/USDC", market_regime_at_exit="greed"))

    # Asset match only
    outcomes = mem_mgr.get_relevant_outcomes(asset="BTC", limit=5)
    assert len(outcomes) == 2
    assert all("BTC" in o["asset"] for o in outcomes)

    # Asset + Regime match
    outcomes_regime = mem_mgr.get_relevant_outcomes(asset="BTC", market_regime="greed", limit=5)
    assert len(outcomes_regime) == 1
    assert outcomes_regime[0]["decision_id"] == "3"

    # Fallback when no match
    outcomes_fallback = mem_mgr.get_relevant_outcomes(asset="SOL", limit=5)
    assert len(outcomes_fallback) == 3


def test_format_for_prompt(mem_mgr):
    mem_mgr.log_outcome(OutcomeRecord(
        decision_id="1", asset="BTC/USDC", 
        realized_pnl_pct=-2.5, was_profitable=False,
        entry_thesis="Bad idea"
    ))
    prompt = mem_mgr.format_for_prompt("BTC")
    assert "[MEMORY]" in prompt
    assert "❌ BTC/USDC" in prompt
    assert "pnl=-2.5%" in prompt


# ============================================================
# TEST: Layer 5 - Evaluation
# ============================================================

def test_evaluation_metrics(mem_mgr):
    # Log some decisions (total 3)
    mem_mgr.log_decision(DecisionRecord(id="d1", timestamp_utc="", asset="BTC", action="buy"))
    mem_mgr.log_decision(DecisionRecord(id="d2", timestamp_utc="", asset="ETH", action="buy"))
    mem_mgr.log_decision(DecisionRecord(id="d3", timestamp_utc="", asset="SOL", action="hold"))

    # Log outcomes (2 executed, 1 win, 1 loss)
    mem_mgr.log_outcome(OutcomeRecord(
        decision_id="d1", asset="BTC", was_profitable=True, realized_pnl_pct=10.0,
        confidence_at_entry=90, market_regime_at_exit="greed"
    ))
    mem_mgr.log_outcome(OutcomeRecord(
        decision_id="d2", asset="ETH", was_profitable=False, realized_pnl_pct=-5.0,
        confidence_at_entry=80, market_regime_at_exit="fear"
    ))

    ev = mem_mgr.compute_evaluation()

    assert ev.total_decisions == 3
    assert ev.total_executed == 2
    assert ev.win_rate == 0.5
    assert ev.avg_pnl_pct == 2.5  # (10-5)/2
    assert ev.avg_confidence_winners == 90.0
    assert ev.avg_confidence_losers == 80.0
    
    assert "BTC" in ev.per_asset
    assert ev.per_asset["BTC"]["win_rate"] == 1.0


# ============================================================
# TEST: Persistence & Migration
# ============================================================

def test_persistence(tmp_path):
    path = tmp_path / "mem.json"
    mgr1 = MemoryManager(path)
    mgr1.log_event("test", "msg")
    
    mgr2 = MemoryManager(path)
    assert len(mgr2._store.events) == 1
    assert mgr2._store.events[0]["message"] == "msg"


def test_v1_migration(tmp_path):
    path = tmp_path / "v1_mem.json"
    # Create fake V1 memory
    v1_data = {
        "lessons_learned": [
            {
                "date": "2026-01-01",
                "action": "BUY BTC/USDC",
                "profit": 5.0,
                "lesson": "Good"
            }
        ]
    }
    with open(path, "w") as f:
        json.dump(v1_data, f)
        
    mgr = MemoryManager(path)
    # V1 lesson should become an outcome
    assert len(mgr._store.outcomes) == 1
    o = mgr._store.outcomes[0]
    assert o["asset"] == "BTC/USDC"
    assert o["realized_pnl_pct"] == 5.0
    assert o["was_profitable"] is True
