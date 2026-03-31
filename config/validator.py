"""
Configuration validator — runs at startup to catch dangerous settings.

Returns a list of issues. Any CRITICAL issue should prevent the bot from starting.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ConfigIssue:
    severity: Severity
    field: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.value}] {self.field}: {self.message}"


def validate_config(config_path: Path) -> list[ConfigIssue]:
    """Validate config.json for dangerous or broken settings."""
    issues: list[ConfigIssue] = []

    if not config_path.exists():
        issues.append(ConfigIssue(Severity.CRITICAL, "config_file", f"File not found: {config_path}"))
        return issues

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        issues.append(ConfigIssue(Severity.CRITICAL, "config_file", f"Invalid JSON: {e}"))
        return issues

    # === SAFETY CHECKS ===

    if not config.get("dry_run", False):
        issues.append(ConfigIssue(
            Severity.WARNING, "dry_run",
            "Live trading is ENABLED. Make sure you know what you are doing."
        ))

    # 6. MOCK validation block on LIVE
    import os
    validation_mode = os.getenv("VALIDATION_MODE", "real").lower()
    if not config.get("dry_run", False) and validation_mode == "mock":
        issues.append(ConfigIssue(
            Severity.CRITICAL, "Validation",
            "Cannot use VALIDATION_MODE=mock when real trading (dry_run=False)."
        ))

    # Stake amount
    stake = config.get("stake_amount")
    if stake == "unlimited":
        issues.append(ConfigIssue(
            Severity.CRITICAL, "stake_amount",
            "'unlimited' stake is extremely dangerous. Set a numeric value."
        ))

    # Wallet size
    wallet = config.get("dry_run_wallet", 0)
    if isinstance(wallet, (int, float)) and wallet > 500:
        issues.append(ConfigIssue(
            Severity.WARNING, "dry_run_wallet",
            f"Large wallet ({wallet}). Verify this is intentional."
        ))

    # Max open trades
    max_trades = config.get("max_open_trades", -1)
    if max_trades == -1 or max_trades > 10:
        issues.append(ConfigIssue(
            Severity.WARNING, "max_open_trades",
            f"max_open_trades is {max_trades}. High values increase exposure."
        ))

    # Stoploss
    stoploss = config.get("stoploss", config.get("stoploss"))
    # Check strategy-level stoploss indirectly via existence
    if stoploss is not None and stoploss > -0.01:
        issues.append(ConfigIssue(
            Severity.WARNING, "stoploss",
            f"Stoploss is {stoploss}, very tight. May cause excessive exits."
        ))

    # API Server
    api = config.get("api_server", {})
    if api.get("enabled", False):
        # 5. Dashboard Binding
        listen_ip = config.get("api_server", {}).get("listen_ip_address", "127.0.0.1")
        if listen_ip in ("0.0.0.0", "::"):
            issues.append(ConfigIssue(
                Severity.CRITICAL, "API Server",
                "Listen IP address is exposed (0.0.0.0). Local-first AI systems should be 127.0.0.1 only."
            ))

        cors = api.get("CORS_origins", [])
        if "*" in cors:
            issues.append(ConfigIssue(
                Severity.WARNING, "api_server.CORS_origins",
                "CORS allows all origins. Restrict to specific origins."
            ))

        if not api.get("username") or not api.get("password"):
            issues.append(ConfigIssue(
                Severity.CRITICAL, "api_server.credentials",
                "Dashboard has no username or password set."
            ))

    # Exchange keys (should not be placeholder values in live mode)
    if not config.get("dry_run", True):
        exchange = config.get("exchange", {})
        if "INSERISCI" in exchange.get("key", ""):
            issues.append(ConfigIssue(
                Severity.CRITICAL, "exchange.key",
                "Exchange API key is a placeholder but dry_run is False."
            ))

    # Telegram
    telegram = config.get("telegram", {})
    if telegram.get("enabled", False) and not telegram.get("token"):
        issues.append(ConfigIssue(
            Severity.WARNING, "telegram.token",
            "Telegram is enabled but no token is set."
        ))

    return issues


def validate_and_report(config_path: Path) -> bool:
    """Run validation and log results. Returns True if no CRITICAL issues."""
    issues = validate_config(config_path)

    if not issues:
        logger.info("✅ Config validation passed — no issues found.")
        return True

    has_critical = False
    for issue in issues:
        if issue.severity == Severity.CRITICAL:
            logger.error(f"🚨 {issue}")
            has_critical = True
        elif issue.severity == Severity.WARNING:
            logger.warning(f"⚠️ {issue}")
        else:
            logger.info(f"ℹ️ {issue}")

    if has_critical:
        logger.error("❌ Config validation FAILED — fix CRITICAL issues before starting.")
    else:
        logger.info("✅ Config validation passed with warnings.")

    return not has_critical
