"""
Test suite for Module 1: Types, Settings, Validator, Logging.
Run: python -m pytest tests/ -v
"""
import json
import os
import sys

import pytest

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.types import (
    Action, AgentMessage, MarketIntelligence, RiskAssessment,
    RiskVerdict, Status, TaskType, TradeProposal,
)
from config.settings import Settings, load_settings
from config.validator import ConfigIssue, Severity, validate_config
from user_data.ai_agents.ollama_brain import AIDecision, parse_ai_response



# ============================================================
# TEST: AI Types & Contracts
# ============================================================

class TestAgentMessage:
    def test_create_message(self):
        msg = AgentMessage(
            agent_name="test", task_type=TaskType.DECISION,
            status=Status.SUCCESS, confidence=80,
            recommended_action=Action.BUY, reason_short="test"
        )
        assert msg.agent_name == "test"
        assert msg.confidence == 80

    def test_serialize_roundtrip(self):
        msg = AgentMessage(
            agent_name="brain", task_type=TaskType.ANALYSIS,
            status=Status.WARNING, asset="BTC/USDC",
            confidence=65, recommended_action=Action.HOLD
        )
        d = msg.to_dict()
        assert d["task_type"] == "analysis"
        assert d["status"] == "warning"
        assert d["recommended_action"] == "hold"

        restored = AgentMessage.from_dict(d)
        assert restored.agent_name == "brain"
        assert restored.task_type == TaskType.ANALYSIS

    def test_to_json(self):
        msg = AgentMessage(
            agent_name="test", task_type=TaskType.RISK,
            status=Status.BLOCKED
        )
        j = msg.to_json()
        parsed = json.loads(j)
        assert parsed["agent_name"] == "test"


class TestMarketIntelligence:
    def test_defaults(self):
        mi = MarketIntelligence(asset="BTC/USDC")
        assert mi.rsi_5m == 50.0
        assert mi.fear_and_greed_value == 50

    def test_serialize(self):
        mi = MarketIntelligence(asset="ETH/USDC", rsi_5m=35.0, close_price=3200.0)
        d = mi.to_dict()
        assert d["asset"] == "ETH/USDC"
        assert d["rsi_5m"] == 35.0


class TestTradeProposal:
    def test_create(self):
        tp = TradeProposal(asset="SOL/USDC", action=Action.BUY, confidence=75, reason="Test")
        assert tp.action == Action.BUY
        d = tp.to_dict()
        assert d["action"] == "buy"


class TestRiskAssessment:
    def test_approved(self):
        tp = TradeProposal(asset="BTC/USDC", action=Action.BUY, confidence=80, reason="strong")
        ra = RiskAssessment(proposal=tp, verdict=RiskVerdict.APPROVED, approved_stake=15.0)
        assert ra.verdict == RiskVerdict.APPROVED
        d = ra.to_dict()
        assert d["verdict"] == "approved"


# ============================================================
# TEST: Settings
# ============================================================

class TestSettings:
    def test_load_settings(self):
        s = load_settings()
        assert isinstance(s, Settings)
        # Check against environment or default
        expected_model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
        assert s.model.model_name == expected_model
        assert s.risk.max_consecutive_losses == 3
        assert s.trading.dry_run  # Must be True in test

    def test_settings_frozen(self):
        s = load_settings()
        with pytest.raises(AttributeError):
            s.risk = None  # type: ignore


# ============================================================
# TEST: Config Validator
# ============================================================

class TestConfigValidator:
    def test_validate_current_config(self):
        from pathlib import Path
        config_path = Path(__file__).parent.parent / "config.json"
        issues = validate_config(config_path)
        critical = [i for i in issues if i.severity == Severity.CRITICAL]
        assert len(critical) == 0, f"Critical issues: {[str(i) for i in critical]}"

    def test_validate_detects_unlimited_stake(self, tmp_path):
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({"stake_amount": "unlimited", "dry_run": True}))
        issues = validate_config(bad_config)
        assert any("unlimited" in i.message for i in issues)

    def test_validate_detects_open_binding(self, tmp_path):
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({
            "api_server": {"enabled": True, "listen_ip_address": "0.0.0.0",
                           "username": "u", "password": "p"}
        }))
        issues = validate_config(bad_config)
        assert any("0.0.0.0" in i.message for i in issues)

    def test_validate_blocks_mock_mode_live(self, tmp_path):
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({"dry_run": False}))
        os.environ["VALIDATION_MODE"] = "mock"
        try:
            issues = validate_config(bad_config)
            assert any("Cannot use VALIDATION_MODE=mock" in i.message for i in issues)
        finally:
            os.environ.pop("VALIDATION_MODE")


# ============================================================
# TEST: AI Response Parser (from V5.0)
# ============================================================

class TestAIParser:
    def test_valid_json_buy(self):
        result = parse_ai_response('{"action":"BUY","confidence":75,"reason":"RSI basso"}')
        assert result["action"] == "BUY"
        assert result["confidence"] == 75

    def test_valid_json_hold(self):
        result = parse_ai_response('{"action":"HOLD","confidence":30,"reason":"incerto"}')
        assert result["action"] == "HOLD"

    def test_json_with_markdown(self):
        result = parse_ai_response('```json\n{"action":"BUY","confidence":80,"reason":"ok"}\n```')
        assert result["action"] == "BUY"

    def test_thinking_block(self):
        result = parse_ai_response('<think>hmm</think>{"action":"HOLD","confidence":50,"reason":"done"}')
        assert result["action"] == "HOLD"

    def test_legacy_format(self):
        result = parse_ai_response("ACTION:BUY CONFIDENCE:85 REASON:Strong momentum")
        assert result["action"] == "BUY"
        assert result["confidence"] == 85

    def test_confidence_clamped(self):
        result = parse_ai_response('{"action":"BUY","confidence":150,"reason":"t"}')
        assert result["confidence"] == 100

    def test_invalid_action_defaults_hold(self):
        result = parse_ai_response('{"action":"SELL","confidence":90,"reason":"t"}')
        assert result["action"] == "HOLD"

    def test_garbage_input(self):
        result = parse_ai_response("not a valid response")
        assert result["action"] == "HOLD"
        assert result["confidence"] == 0

    def test_empty_input(self):
        result = parse_ai_response("")
        assert result["action"] == "HOLD"


# ============================================================
# TEST: Security Checks
# ============================================================

class TestSecurity:
    def test_config_not_exposed(self):
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        with open(config_path) as f:
            config = json.load(f)
        assert config.get("dry_run") is True
        assert config["api_server"]["listen_ip_address"] != "0.0.0.0"
        assert "*" not in config["api_server"]["CORS_origins"]

    def test_gitignore_protects_secrets(self):
        gi_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".gitignore")
        content = open(gi_path).read()
        assert ".env" in content
        assert "*.sqlite" in content

    def test_env_example_exists(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.example")
        assert os.path.exists(path)
