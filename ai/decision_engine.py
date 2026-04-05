"""
Decision Engine V11.5 — The Ultimate Autonomous Scaler.
Integrated patterns from Claude Code (src/):
1. Structured Output Retry (MAX_STRUCTURED_RETRIES)
2. Memory Pruning & Indexing (Context Window Management)
3. Cost-Aware Quota Guard (Early Warning)
4. Technical Engine Offloading
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
from ai.technical_engine import TechnicalEngine

logger = logging.getLogger("ai.decision_engine")

# ── System Prompt V4: The Gold Standard ──
SYSTEM_PROMPT = """You are a quantitative crypto trading evaluator for high-volatility memecoins.
You receive technical market data and MUST return a single valid JSON object.

CRITICAL FORMATTING RULES:
1. You MAY use <think>...</think> tags for internal reasoning BEFORE the JSON.
2. After </think>, output ONLY the JSON object. Nothing else.
3. NEVER wrap JSON in markdown code blocks (no ```json).

JSON SCHEMA:
{
  "decision": "buy" | "hold",
  "confidence": <integer 0-100>,
  "thesis": "<max 80 chars, ASCII only>",
  "inner_monologue": "<your reasoning>",
  "technical_basis": ["<indicator detail>", ...],
  "news_basis": ["<news detail>", ...],
  "risk_flags": ["<risk>", ...]
}

DECISION GUIDELINES:
- RSI < 30 on 5m AND MACD turning positive → strong BUY signal (70+)
- RSI < 25 → extreme oversold, BUY (75+)
- In TREND_UP with RSI 40-60, favor momentum BUY
- When uncertain, output HOLD with confidence < 40
- Never fabricate data. If data is missing, flag in risk_flags."""

RETRY_PROMPT_TEMPLATE = """Your previous response was not valid JSON. Error: {error}
You MUST respond with ONLY a valid JSON object matching this schema:
{{"decision":"buy","confidence":75,"thesis":"reason","inner_monologue":"reasoning","technical_basis":[],"news_basis":[],"risk_flags":[]}}
Respond with the JSON NOW:"""

def evaluate(intelligence: MarketIntelligence, repo=None) -> TradeDecision:
    """Evaluate a single asset and return a structured TradeDecision.
    Always returns a valid TradeDecision."""
    settings = get_settings()
    vmode = settings.model.validation_mode

    # 1. FAST OFFLINE MOCK MODE
    if vmode == ValidationMode.MOCK.value:
        decision = _evaluate_mock(intelligence)
        decision.data_quality = _assess_data_quality(intelligence)
        return decision
        
    # 2. CACHED INFERENCE MODE
    if vmode == ValidationMode.CACHED.value:
        cached_decision = get_cached_decision(intelligence)
        if cached_decision:
            cached_decision.data_quality = _assess_data_quality(intelligence)
            cached_decision.staleness_seconds = intelligence.research_staleness_seconds
            return cached_decision

    # 3. COST-AWARE GUARD (Jewel from src/services/claudeAiLimits.ts)
    # Skip expensive AI if market is neutral and price is flat
    if abs(intelligence.pnl_24h) < 0.4 and 44 <= intelligence.rsi_5m <= 56:
        logger.info(f"[{intelligence.asset}] [COST-AWARE] Neutral market. Using technical fallback.")
        return _technical_fallback(intelligence)

    # 4. REAL INFERENCE MODE
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
        return _technical_fallback(intelligence)

    # Parse and validate
    decision = _parse_response(raw_response, intelligence)
    decision.data_quality = _assess_data_quality(intelligence)
    decision.staleness_seconds = intelligence.research_staleness_seconds
    decision.requires_risk_review = (
        decision.decision == Action.BUY or
        decision.confidence > 80 or
        intelligence.macro_risk_level > 0.7
    )

    # 5. SWARM CONSENSUS (For high-confidence BUYs)
    if decision.decision == Action.BUY and decision.confidence >= 70:
        decision = _validate_with_swarm(decision, intelligence)

    # Save to cache
    if vmode in (ValidationMode.REAL.value, ValidationMode.CACHED.value):
        save_decision_to_cache(intelligence, decision)

    # Save to SuperBrain
    try:
        from storage.superbrain import get_superbrain
        brain = get_superbrain()
        brain.remember_market_signal(
            intelligence.asset,
            f"Decision: {decision.decision.value} (conf: {decision.confidence}%) — {decision.thesis[:100]}",
            confidence=decision.confidence
        )
    except Exception:
        pass

    logger.info(f"[{intelligence.asset}] Result: {decision.decision.value} (Conf: {decision.confidence}%)")
    return decision

def _evaluate_mock(intel: MarketIntelligence) -> TradeDecision:
    if intel.rsi_5m < 30 and intel.macd_5m > 0:
        return TradeDecision(
            asset=intel.asset, decision=Action.BUY, confidence=85,
            thesis="Mock: deterministic buy trigger",
            inner_monologue="RSI < 30 + MACD bullish cross.",
            risk_flags=["mock_mode"]
        )
    return TradeDecision.default_hold(intel.asset, "Mock: no signal")

def _build_user_message(intel: MarketIntelligence, repo=None) -> str:
    """Construct the final prompt string from MarketIntelligence.
    Pattern: Context Window Management (MAX_PROMPT_CHARS).
    """
    MAX_PROMPT_CHARS = 27000
    trend_5m = "bullish" if intel.macd_5m > 0 else "bearish"
    
    lines = [
        f"ASSET: {intel.asset}",
        f"PRICE: {intel.close_price:.2f}",
        f"RSI_5m: {intel.rsi_5m:.1f} | MACD_5m: {intel.macd_5m:.4f} ({trend_5m})",
        f"FEAR_GREED: {intel.fear_and_greed_value}/100 ({intel.market_regime})",
        f"NEWS_SENTIMENT: {intel.news_sentiment_score:+.2f} ({intel.news_count} items)",
        f"MACRO_RISK: {intel.macro_risk_level:.2f}"
    ]

    if intel.top_headlines:
        lines.append("HEADLINES: " + " | ".join(intel.top_headlines[:2]))

    # --- MEMORY PRUNING & INDEXING (Claude Code Pattern: src/services/autoDream) ---
    try:
        from storage.superbrain import get_superbrain
        brain = get_superbrain()
        current_chars = len("\n".join(lines))
        budget = MAX_PROMPT_CHARS - current_chars

        # 1. Asset Context
        if budget > 2000:
            ctx = brain.get_market_context(intel.asset)
            if ctx:
                lines.append("\nCONTEXT: " + ctx[:800])
                budget -= 800

        # 2. Golden Rules (Pruned)
        if budget > 1500:
            core_rules = brain.get_core_rules()
            if core_rules:
                rules = [r.strip() for r in core_rules.split("\n") if r.strip()]
                if len(rules) > 12:
                    rules = [r for r in rules if "GOLDEN" in r.upper() or "!!!" in r][:15]
                
                drift_warning = ""
                if (intel.research_staleness_seconds or 0) > 1800:
                    drift_warning = "\n⚠️ DRIFT WARNING: Memory might be stale (>30m)."
                
                lines.append("\n=== GOLDEN RULES ===")
                lines.append("\n".join(rules))
                if drift_warning: lines.append(drift_warning)
                lines.append("====================")
    except Exception:
        pass

    lines.append(f"DATA_QUALITY: {intel.data_quality}")
    lines.append("Respond with JSON only.")
    return "\n".join(lines)

def _call_model(user_msg: str, model: str, base_url: str, timeout: int, max_retries: int) -> Optional[str]:
    url = f"{base_url}/api/chat"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg}
    ]
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json={
                "model": model, "messages": messages, "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1000}
            }, timeout=timeout)
            resp.raise_for_status()
            raw_content = resp.json().get("message", {}).get("content", "")

            # Structured Output Retry Loop (Jewel from QueryEngine.ts)
            for retry_idx in range(2):
                test_content = raw_content.strip()
                if "</think>" in test_content: test_content = test_content.split("</think>")[-1].strip()
                test_content = re.sub(r'^```(?:json)?\s*', '', test_content)
                test_content = re.sub(r'\s*```$', '', test_content)
                
                try:
                    json.loads(test_content)
                    return raw_content # Success
                except json.JSONDecodeError as e:
                    if retry_idx == 0:
                        logger.warning(f"JSON Parse fail, retrying with feedback: {e}")
                        messages.append({"role": "assistant", "content": raw_content})
                        messages.append({"role": "user", "content": RETRY_PROMPT_TEMPLATE.format(error=str(e))})
                        retry_resp = requests.post(url, json={
                            "model": model, "messages": messages, "stream": False,
                            "options": {"temperature": 0.05}
                        }, timeout=timeout)
                        raw_content = retry_resp.json().get("message", {}).get("content", "")
                    else: break
            return raw_content
        except Exception as e:
            logger.warning(f"Model call failed (attempt {attempt+1}): {e}")
            time.sleep(1)
    return None

def _parse_response(raw: str, intel: MarketIntelligence) -> TradeDecision:
    cleaned = raw.strip()
    thinking = ""
    if "</think>" in cleaned:
        parts = cleaned.split("</think>")
        thinking = parts[0].replace("<think>", "").strip()
        cleaned = parts[-1].strip()

    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned).strip()

    # Try different parse levels
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return _validate_parsed(data, intel.asset, thinking)
        except Exception: pass
    
    return TradeDecision.default_hold(intel.asset, "Parse failure: fallback to hold")

def _validate_parsed(data: dict, asset: str, thinking: str) -> TradeDecision:
    raw_dec = str(data.get("decision", "hold")).lower()
    return TradeDecision(
        asset=asset,
        decision=Action.BUY if raw_dec == "buy" else Action.HOLD,
        confidence=min(100, max(0, int(data.get("confidence", 0)))),
        thesis=str(data.get("thesis", ""))[:100],
        inner_monologue=thinking or str(data.get("inner_monologue", ""))[:1000],
        technical_basis=data.get("technical_basis", []),
        news_basis=data.get("news_basis", []),
        risk_flags=data.get("risk_flags", [])
    )

def _technical_fallback(intel: MarketIntelligence) -> TradeDecision:
    if intel.rsi_5m < 35 and intel.macd_5m > 0:
        return TradeDecision(
            asset=intel.asset, decision=Action.BUY, confidence=45,
            thesis="Technical Fallback: RSI Oversold + MACD positive",
            data_quality=DataQuality.MEDIUM
        )
    return TradeDecision.default_hold(intel.asset, "Technical Fallback: No clear signal")

def _assess_data_quality(intel: MarketIntelligence) -> DataQuality:
    if intel.research_staleness_seconds < 300: return DataQuality.HIGH
    if intel.research_staleness_seconds < 900: return DataQuality.MEDIUM
    return DataQuality.LOW

def _validate_with_swarm(decision: TradeDecision, intel: MarketIntelligence) -> TradeDecision:
    try:
        from ai.openrouter_client import call_swarm_consensus
        messages = [
            {"role": "system", "content": "You are a crypto analyst. Reply ONLY 'BUY' or 'HOLD' with brief reason."},
            {"role": "user", "content": f"Asset: {intel.asset}, Price: {intel.close_price}, RSI: {intel.rsi_5m:.1f}, Thesis: {decision.thesis}"}
        ]
        results = call_swarm_consensus(messages, max_models=2, timeout=10)
        if not results: return decision
        buy_votes = sum(1 for r in results.values() if "BUY" in r.upper())
        if buy_votes < 1:
            decision.decision = Action.HOLD
            decision.confidence = 30
            decision.thesis = f"Swarm REJECTED (0/2 BUY). Original thesis: {decision.thesis}"
        else:
            decision.thesis += f" [Swarm validated: {buy_votes} BUY]"
        return decision
    except Exception: return decision
