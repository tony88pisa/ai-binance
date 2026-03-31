"""
Structured logging setup for the AI trading platform.

Provides a JSON-capable logger and helper functions for
consistent, machine-parseable log output.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Outputs log records as JSON lines for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Add structured data if attached
        if hasattr(record, "data") and record.data:
            log_entry["data"] = record.data
        if record.exc_info and record.exc_info[1]:
            log_entry["error"] = str(record.exc_info[1])
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: int = logging.INFO, json_output: bool = False) -> None:
    """Configure root logger. Use json_output=True for structured logs."""
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_output:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))

    root.addHandler(handler)


def log_event(logger: logging.Logger, level: int, msg: str, **data: Any) -> None:
    """Log a message with optional structured data attached."""
    record = logger.makeRecord(
        logger.name, level, "(structured)", 0, msg, (), None
    )
    record.data = data if data else None  # type: ignore
    logger.handle(record)


def log_trade_decision(logger: logging.Logger, asset: str, action: str,
                       confidence: int, reason: str, source: str = "ai") -> None:
    """Convenience function to log a trade decision consistently."""
    log_event(
        logger, logging.INFO,
        f"[{source.upper()}] {asset}: {action} conf={confidence}",
        asset=asset, action=action, confidence=confidence,
        reason=reason, source=source
    )
