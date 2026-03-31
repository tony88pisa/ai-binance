"""
Decision Engine V2 — Structured AI decision making.

Accepts MarketIntelligence, produces TradeDecision.
No data fetching. No side effects. Pure evaluation.

The model (qwen3:8b) receives structured input and must return JSON.
Output is validated, parsed, and sanitized. Invalid outputs → default HOLD.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from ai.types import (
    Action, DataQuality, MarketIntelligence, TimeHorizon, TradeDecision, ValidationMode
)
from config.settings import get_settings
from ai.cache import get_cached_decision, save_decision_to_cache

logger = logging.getLogger("ai.decision_engine")

# System prompt: brief, structural, no roleplay
SYSTEM_PROMPT = """You are a quantitative trading evaluator. You receive market data and return a JSON decision.

RULES:
- Output ONLY a valid JSON object. No markdown, no explanation, no text outside JSON.
- Format:
{"decision":"buy","confidence":75,"thesis":"one line reason","technical_basis":["RSI at 28"],"news_basis":["ETF rumor"],"risk_flags":["extreme_fear"]}
- decision: only "buy" or "hold"
- confidence: integer 0-100
- thesis: max 80 chars, ASCII only
- technical_basis: array of strings (may be empty)
- news_basis: array of strings (may be empty)
- risk_flags: array of strings (may be empty)
- If uncertain, output hold with low confidence.
- Never fabricate data. If information is missing, say so."""


def evaluate(intelligence: MarketIntelligence, repo=None) -> TradeDecision:
    """Evaluate a single asset and return a structured TradeDecision.
    Never raises. Always returns a valid TradeDecision."""
    settings = get_settings()
    vmode = settings.model.validation_mode

    # 1. FAST OFFLINE MOCK MODE
    if vmode == ValidationMode.MOCK.value:
        logger.debug(f"[{intelligence.asset}] [MOCK MODE] Using fast deterministic mock")
        decision = _evaluate_mock(intelligence)
        decision.data_quality = _assess_data_quality(intelligence)
        decision.requires_risk_review = True
        return decision
        
    # 2. CACHED INFERENCE MODE
    if vmode == ValidationMode.CACHED.value:
        cached_decision = get_cached_decision(intelligence)
        if cached_decision:
            logger.info(f"[{intelligence.asset}] [CACHED MODE] Using cached AI output")
            # Always copy fresh staleness/quality
            cached_decision.data_quality = _assess_data_quality(intelligence)
            cached_decision.staleness_seconds = intelligence.research_staleness_seconds
            return cached_decision
        logger.debug(f"[{intelligence.asset}] [CACHED MODE] Cache miss. Falling back to REAL inference.")

    # 3. REAL INFERENCE MODE (or CACHED miss)
    user_msg = _build_user_message(intelligence, repo)

    # Call model
    raw_response = _call_model(
        user_msg,
        model=settings.model.model_name,
        base_url=settings.model.base_url,
        timeout=settings.model.timeout_seconds,
        max_retries=settings.model.max_retries,
    )

    if raw_response is None:
        logger.warning(f"[{intelligence.asset}] [{vmode.upper()} MODE] Model unreachable, using technical fallback")
        return _technical_fallback(intelligence)

    # Parse and validate
    decision = _parse_response(raw_response, intelligence)

    # Attach data quality and staleness
    decision.data_quality = _assess_data_quality(intelligence)
    decision.staleness_seconds = intelligence.research_staleness_seconds
    decision.requires_risk_review = (
        decision.decision == Action.BUY or
        decision.confidence > 80 or
        intelligence.macro_risk_level > 0.7
    )

    # Save to cache if we just did a REAL inference
    if vmode in (ValidationMode.REAL.value, ValidationMode.CACHED.value):
        save_decision_to_cache(intelligence, decision)

    logger.info(
        f"[{intelligence.asset}] [{vmode.upper()} MODE] decision={decision.decision.value} "
        f"conf={decision.confidence} quality={decision.data_quality.value} "
        f"thesis={decision.thesis[:60]}"
    )

    return decision

def _evaluate_mock(intel: MarketIntelligence) -> TradeDecision:
    """Deterministic, lightning fast evaluation for backtest/integration testing."""
    # Deterministic buy if RSI is extremely low
    if intel.rsi_5m < 30 and intel.macd_5m > 0:
        return TradeDecision(
            asset=intel.asset,
            decision=Action.BUY,
            confidence=85,
            thesis="Mock: deterministic mock buy trigger",
            risk_flags=["mock_mode_active"]
        )
    return TradeDecision.default_hold(
        intel.asset, 
        "Mock: deterministic mock hold trigger"
    )


def _build_user_message(intel: MarketIntelligence, repo=None) -> str:
    """Build structured, concise input for the model. No prose."""
    trend_5m = "bullish" if intel.macd_5m > 0 else "bearish"
    trend_1h = "bullish" if intel.macd_1h > 0 else "bearish"

    # Technical block
    lines = [
        f"ASSET: {intel.asset}",
        f"PRICE: {intel.close_price:.2f}",
        f"RSI_5m: {intel.rsi_5m:.1f} | MACD_5m: {intel.macd_5m:.4f} ({trend_5m})",
        f"RSI_1h: {intel.rsi_1h:.1f} | MACD_1h: {intel.macd_1h:.4f} ({trend_1h})",
    ]

    # Sentiment block
    lines.append(f"FEAR_GREED: {intel.fear_and_greed_value}/100 ({intel.market_regime})")
    lines.append(f"NEWS_SENTIMENT: {intel.news_sentiment_score:+.2f} ({intel.news_count} items)")
    lines.append(f"MACRO_RISK: {intel.macro_risk_level:.2f}")

    if intel.macro_risk_flags:
        lines.append(f"RISK_FLAGS: {', '.join(intel.macro_risk_flags[:3])}")

    if intel.top_headlines:
        lines.append("HEADLINES: " + " | ".join(intel.top_headlines[:3]))

    if intel.historical_lessons:
        lines.append(f"MEMORY: {intel.historical_lessons[:200]}")

    if repo:
        try:
            active_skills = [s for s in repo.list_skill_candidates() if s.get("status") == "approved"]
            if active_skills:
                lines.append("\nEVOLVED RULES (Must follow strict entry conditions):")
                for s in active_skills:
                    rule = s.get("prompt_rule")
                    if rule:
                        lines.append("- " + rule)
        except Exception as e:
            logger.error(f"Failed to load skills: {e}")

    lines.append(f"DATA_QUALITY: {intel.data_quality}")
    lines.append("Respond with JSON only.")

    return "\n".join(lines)


def _call_model(user_msg: str, model: str, base_url: str,
                timeout: int, max_retries: int) -> Optional[str]:
    """Call Ollama and return raw response text. Returns None on total failure."""
    url = f"{base_url}/api/chat"

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                url,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg}
                    ],
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0.1, "num_predict": 200},
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "")
        except requests.exceptions.Timeout:
            logger.warning(f"Model timeout (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            logger.warning(f"Model error (attempt {attempt + 1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            time.sleep(2)

    return None


def _parse_response(raw: str, intel: MarketIntelligence) -> TradeDecision:
    """Parse model response into TradeDecision. Multi-stage with fallback."""
    cleaned = raw.strip()

    # Strip thinking blocks
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1].strip()

    # Strip markdown fences
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    # Stage 1: Direct JSON parse
    parsed = _try_json_parse(cleaned)
    if parsed:
        return _validate_parsed(parsed, intel.asset)

    # Stage 2: Extract first JSON object from text
    match = re.search(r'\{[^{}]+\}', cleaned)
    if match:
        parsed = _try_json_parse(match.group())
        if parsed:
            return _validate_parsed(parsed, intel.asset)

    # Stage 3: Legacy text format fallback
    action_match = re.search(r'(?:ACTION|decision)[:\s]*(BUY|HOLD)', cleaned, re.IGNORECASE)
    conf_match = re.search(r'(?:CONFIDENCE|confidence)[:\s]*(\d+)', cleaned, re.IGNORECASE)
    if action_match and conf_match:
        return TradeDecision(
            asset=intel.asset,
            decision=Action.BUY if action_match.group(1).upper() == "BUY" else Action.HOLD,
            confidence=min(100, max(0, int(conf_match.group(1)))),
            thesis=f"Legacy format parse: {cleaned[:60]}",
        )

    # Stage 4: Total parse failure
    logger.warning(f"[{intel.asset}] Parse failure, raw: {cleaned[:80]}")
    return TradeDecision.default_hold(intel.asset, f"Parse failure: {cleaned[:40]}")


def _try_json_parse(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _validate_parsed(data: dict, asset: str) -> TradeDecision:
    """Validate and normalize a parsed JSON dict into TradeDecision."""
    # Decision
    raw_decision = str(data.get("decision", data.get("action", "hold"))).lower()
    decision = Action.BUY if raw_decision == "buy" else Action.HOLD

    # Confidence
    confidence = int(data.get("confidence", 0))
    confidence = min(100, max(0, confidence))

    # Thesis
    thesis = _sanitize_str(data.get("thesis", data.get("reason", "")), max_len=100)

    # Lists
    technical_basis = _sanitize_list(data.get("technical_basis", []))
    news_basis = _sanitize_list(data.get("news_basis", []))
    risk_flags = _sanitize_list(data.get("risk_flags", []))

    return TradeDecision(
        asset=asset,
        decision=decision,
        confidence=confidence,
        thesis=thesis,
        technical_basis=technical_basis,
        news_basis=news_basis,
        risk_flags=risk_flags,
    )


def _technical_fallback(intel: MarketIntelligence) -> TradeDecision:
    """Pure technical fallback when model is unreachable."""
    basis = []
    if intel.rsi_5m < 35:
        basis.append(f"RSI_5m oversold at {intel.rsi_5m:.0f}")
    if intel.macd_5m > 0:
        basis.append("MACD_5m bullish")
    if intel.rsi_1h < 45:
        basis.append(f"RSI_1h low at {intel.rsi_1h:.0f}")

    if intel.rsi_5m < 35 and intel.macd_5m > 0 and intel.rsi_1h < 45:
        return TradeDecision(
            asset=intel.asset, decision=Action.BUY, confidence=50,
            thesis="Technical fallback: oversold bounce setup",
            technical_basis=basis,
            risk_flags=["model_unreachable"],
            data_quality=DataQuality.LOW,
        )
    if intel.rsi_5m < 30 and intel.rsi_1h < 40:
        return TradeDecision(
            asset=intel.asset, decision=Action.BUY, confidence=45,
            thesis="Technical fallback: deep oversold multi-TF",
            technical_basis=basis,
            risk_flags=["model_unreachable"],
            data_quality=DataQuality.LOW,
        )
    return TradeDecision.default_hold(
        intel.asset, "Technical fallback: no clear signal"
    )


def _assess_data_quality(intel: MarketIntelligence) -> DataQuality:
    """Assess the quality of input data."""
    if intel.research_staleness_seconds < 300 and intel.news_count > 0:
        return DataQuality.HIGH
    if intel.research_staleness_seconds < 900:
        return DataQuality.MEDIUM
    return DataQuality.LOW


def _sanitize_str(s: str, max_len: int = 100) -> str:
    if not isinstance(s, str):
        s = str(s)
    return re.sub(r'[^\x20-\x7E]', '', s)[:max_len]


def _sanitize_list(lst: list, max_items: int = 5) -> list[str]:
    if not isinstance(lst, list):
        return []
    return [_sanitize_str(str(item), 80) for item in lst[:max_items]]
