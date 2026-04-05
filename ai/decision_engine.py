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

# ── System Prompt V3: Structured Output Enforcement ──
# Ispirato al pattern "Structured Output + Retry" di Claude Code (QueryEngine.ts)
# Key techniques:
#   1. JSON-only enforcement con example esplicito
#   2. Thinking separation: <think> tag per reasoning, JSON fuori
#   3. Reward signal: "confidence bonus" per output ben formattato
SYSTEM_PROMPT = """You are a quantitative crypto trading evaluator for high-volatility memecoins.
You receive technical market data and MUST return a single valid JSON object.

CRITICAL FORMATTING RULES:
1. You MAY use <think>...</think> tags for internal reasoning BEFORE the JSON.
2. After </think>, output ONLY the JSON object. Nothing else.
3. If you don't want to think, just output the JSON directly.
4. NEVER wrap JSON in markdown code blocks (no ```json).

JSON SCHEMA (strict — every field required):
{
  "decision": "buy" | "hold",
  "confidence": <integer 0-100>,
  "thesis": "<max 80 chars, ASCII only, one line>",
  "inner_monologue": "<your step-by-step reasoning>",
  "technical_basis": ["<indicator detail>", ...],
  "news_basis": ["<news detail>", ...],
  "risk_flags": ["<risk>", ...]
}

DECISION GUIDELINES:
- RSI < 30 on 5m AND MACD turning positive → strong BUY signal (confidence 70+)
- RSI < 25 → extreme oversold, BUY with confidence 75+
- RSI 30-45 with MACD bullish crossover → moderate BUY (55-70)
- RSI 45-55, MACD flat → HOLD (confidence 30-50)
- RSI > 70 → overbought, HOLD or caution
- In TREND_UP with RSI 40-60, favor momentum BUY with moderate confidence
- When uncertain, output HOLD with confidence < 40
- Never fabricate data. If data is missing, lower confidence and flag in risk_flags.
- Be aggressive on oversold bounces — these are memecoins, volatility IS the edge."""

# Retry prompt quando il parse fallisce (pattern "Structured Output Retry" da Claude Code)
RETRY_PROMPT_TEMPLATE = """Your previous response was not valid JSON. Error: {error}

You MUST respond with ONLY a valid JSON object matching this schema:
{{"decision":"buy","confidence":75,"thesis":"reason","inner_monologue":"reasoning","technical_basis":[],"news_basis":[],"risk_flags":[]}}

Respond with the JSON NOW:"""


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

    # 3.5 SWARM CONSENSUS VALIDATION (solo per BUY ad alta confidenza)
    if decision.decision == Action.BUY and decision.confidence >= 70:
        decision = _validate_with_swarm(decision, intelligence)

    # Save to cache if we just did a REAL inference
    if vmode in (ValidationMode.REAL.value, ValidationMode.CACHED.value):
        save_decision_to_cache(intelligence, decision)

    # 4. FINAL LOG & RETURN
    logger.info(
        f"[{intelligence.asset}] [{vmode.upper()} MODE] decision={decision.decision.value} "
        f"conf={decision.confidence} quality={decision.data_quality.value} "
        f"swarm={'validated' if getattr(decision, '_swarm_validated', False) else 'skipped'} "
        f"thesis={decision.thesis[:60]}"
    )

    # Salva decisione su SuperBrain
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
            inner_monologue="L'RSI è estremamente basso (<30) e il MACD mostra i primi segnali di divergenza rialzista. Le condizioni tecniche suggeriscono un rimbalzo imminente (Mock Logic).",
            risk_flags=["mock_mode_active"]
        )
    return TradeDecision.default_hold(
        intel.asset, 
        "Mock: deterministic mock hold trigger"
    )


def _estimate_tokens(text: str, bytes_per_token: int = 4) -> int:
    """Rough token estimation (pattern from tokenEstimation.ts).
    JSON-like content uses ~2 bytes/token, prose ~4 bytes/token."""
    return max(1, len(text) // bytes_per_token)


def _build_user_message(intel: MarketIntelligence, repo=None) -> str:
    """Build structured, concise input for the model.
    
    V3: Token Budget Guard (pattern da tokenEstimation.ts di Claude Code).
    Stima i token del prompt e tronca intelligentemente se supera il 80%
    della context window di Gemma (8192 token).
    
    Memory Drift Caveat (pattern da memoryTypes.ts):
    Le regole di SuperBrain possono diventare stale. Aggiungiamo un warning
    se i dati sono vecchi, così Gemma non li segue ciecamente.
    """
    settings = get_settings()
    trend_5m = "bullish" if intel.macd_5m > 0 else "bearish"
    trend_1h = "bullish" if intel.macd_1h > 0 else "bearish"

    # ── Token Budget: contesto Gemma = ~8192 token ──
    # System prompt ≈ 400 token, riserviamo 1000 per output
    # Budget prompt utente = 8192 - 400 - 1000 = 6792 token ≈ 27168 chars
    MAX_PROMPT_CHARS = 27000  # ~6750 token a 4 byte/token
    
    # Technical block (priorità ALTA — sempre incluso)
    lines = [
        f"ASSET: {intel.asset}",
        f"PRICE: {intel.close_price:.2f}",
        f"RSI_5m: {intel.rsi_5m:.1f} | MACD_5m: {intel.macd_5m:.4f} ({trend_5m})",
        f"RSI_1h: {intel.rsi_1h:.1f} | MACD_1h: {intel.macd_1h:.4f} ({trend_1h})",
    ]

    # Sentiment block (priorità ALTA)
    lines.append(f"FEAR_GREED: {intel.fear_and_greed_value}/100 ({intel.market_regime})")
    lines.append(f"NEWS_SENTIMENT: {intel.news_sentiment_score:+.2f} ({intel.news_count} items)")
    lines.append(f"MACRO_RISK: {intel.macro_risk_level:.2f}")

    if intel.macro_risk_flags:
        lines.append(f"RISK_FLAGS: {', '.join(intel.macro_risk_flags[:3])}")

    if intel.top_headlines:
        lines.append("HEADLINES: " + " | ".join(intel.top_headlines[:2]))  # Max 2 headlines (token saving)

    if intel.historical_lessons:
        lines.append(f"SHORT-TERM DB MEMORY: {intel.historical_lessons[:150]}")  # Ridotto da 200

    # ── SuperBrain Context con Memory Drift Caveat ──
    # Pattern da memoryTypes.ts: "Memory records can become stale.
    # Before acting on memory, verify against current state."
    try:
        from storage.superbrain import get_superbrain
        brain = get_superbrain()

        # Token budget tracking per sezioni opzionali
        core_chars = len("\n".join(lines))
        remaining_budget = MAX_PROMPT_CHARS - core_chars

        # Semantic market context for this asset (priorità MEDIA)
        if remaining_budget > 2000:
            market_ctx = brain.get_market_context(intel.asset)
            if market_ctx:
                # Memory Drift: tronca contesto troppo lungo
                ctx_truncated = market_ctx[:min(800, remaining_budget // 4)]
                lines.append("\n" + ctx_truncated)
                remaining_budget -= len(ctx_truncated)

        # Golden Rules con Drift Warning (priorità ALTA)
        if remaining_budget > 1500:
            core_rules = brain.get_core_rules()
            if core_rules:
                # Memory Drift Caveat: avvisa se le regole potrebbero essere stale
                drift_warning = ""
                if intel.research_staleness_seconds > 1800:  # > 30 min
                    drift_warning = "\n⚠️ DRIFT WARNING: rules may be stale (>30min old). Verify against current RSI/MACD before following."
                
                rules_truncated = core_rules[:min(600, remaining_budget // 3)]
                lines.append("\n=== GOLDEN RULES (from past experience) ===")
                lines.append(rules_truncated)
                if drift_warning:
                    lines.append(drift_warning)
                lines.append("==========================================")
                remaining_budget -= len(rules_truncated)

        # Tactical strategy (priorità BASSA — tagliata per prima se budget stretto)
        if remaining_budget > 1000:
            strategy = brain.get_current_strategy()
            if strategy:
                strat_budget = min(300, remaining_budget // 3)
                lines.append("\n=== TACTICAL STRATEGY (Dream Agent) ===")
                lines.append(strategy[:strat_budget])
                lines.append("========================================")
    except Exception as e:
        logger.error(f"SuperBrain context retrieval failed: {e}")


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
    lines.append(f"MODE: {settings.exchange.mode.upper()} (Exploration encouraged)")
    lines.append("Respond with JSON only.")

    return "\n".join(lines)


def _call_model(user_msg: str, model: str, base_url: str,
                timeout: int, max_retries: int) -> Optional[str]:
    """Call Ollama with Structured Output Retry Loop.
    Pattern: se il modello non produce JSON valido, ri-prova con feedback
    esatto dell'errore (ispirato a QueryEngine.ts MAX_STRUCTURED_OUTPUT_RETRIES).
    """
    url = f"{base_url}/api/chat"
    
    try:
        from ai.mcp_client import TenguMCPClient
        mcp = TenguMCPClient()
        tools_schema = mcp.get_ollama_tools_schema()
    except Exception as e:
        tools_schema = None
        mcp = None
        logger.error(f"Errore caricamento MCP Client: {e}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg}
    ]

    MAX_STRUCTURED_RETRIES = 3  # Retry con feedback se JSON non valido

    for attempt in range(max_retries):
        try:
            # Active Agentic Loop (supports up to 3 tool calls per evaluation)
            for _step in range(4):
                t_start = time.time()
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1000,
                        # Forza la generazione a iniziare con { (JSON Prefill technique)
                        "stop": ["\n\n\n"],
                    },
                }
                if tools_schema:
                    payload["tools"] = tools_schema

                resp = requests.post(url, json=payload, timeout=timeout)
                resp.raise_for_status()
                duration_ms = int((time.time() - t_start) * 1000)
                resp_data = resp.json()
                
                # Track cost
                try:
                    from telemetry.cost_tracker import get_cost_tracker
                    tracker = get_cost_tracker()
                    usage = resp_data.get("eval_count", 0)
                    prompt_tokens = resp_data.get("prompt_eval_count", 0)
                    tracker.record_call(
                        model=model, caller="decision_engine",
                        input_tokens=prompt_tokens, output_tokens=usage,
                        duration_ms=duration_ms, success=True
                    )
                except Exception:
                    pass
                
                message = resp_data.get("message", {})
                
                # Check for tool_calls
                if "tool_calls" in message and message["tool_calls"] and mcp:
                    messages.append(message)
                    for tool_call in message["tool_calls"]:
                        tool_name = tool_call["function"]["name"]
                        args = tool_call["function"].get("arguments", {})
                        tool_response = mcp.execute_tool(tool_name, args)
                        messages.append({"role": "tool", "name": tool_name, "content": tool_response})
                    continue
                else:
                    raw_content = message.get("content", "")
                    
                    # ── Structured Output Retry Loop ──
                    # Se il contenuto non è JSON valido, ri-prova con feedback
                    for retry_idx in range(MAX_STRUCTURED_RETRIES):
                        # Quick validation: can we extract JSON?
                        test_content = raw_content.strip()
                        if "</think>" in test_content:
                            test_content = test_content.split("</think>")[-1].strip()
                        test_content = re.sub(r'^```(?:json)?\s*', '', test_content)
                        test_content = re.sub(r'\s*```$', '', test_content)
                        
                        # Try direct parse
                        try:
                            json.loads(test_content)
                            logger.debug(f"JSON valido al tentativo {retry_idx + 1}")
                            return raw_content  # JSON valido!
                        except json.JSONDecodeError as je:
                            pass
                        
                        # Try regex extraction
                        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', test_content)
                        if json_match:
                            try:
                                json.loads(json_match.group())
                                return raw_content  # JSON estraibile
                            except json.JSONDecodeError:
                                pass
                        
                        if retry_idx < MAX_STRUCTURED_RETRIES - 1:
                            # Feedback retry: invia all'AI l'errore esatto
                            error_detail = f"Could not parse JSON from: {test_content[:100]}..."
                            retry_msg = RETRY_PROMPT_TEMPLATE.format(error=error_detail)
                            messages.append({"role": "assistant", "content": raw_content})
                            messages.append({"role": "user", "content": retry_msg})
                            
                            logger.info(f"Structured Output Retry {retry_idx + 1}/{MAX_STRUCTURED_RETRIES}")
                            
                            # Re-call the model
                            retry_payload = {
                                "model": model, "messages": messages,
                                "stream": False,
                                "options": {"temperature": 0.05, "num_predict": 500},
                            }
                            retry_resp = requests.post(url, json=retry_payload, timeout=timeout)
                            retry_resp.raise_for_status()
                            raw_content = retry_resp.json().get("message", {}).get("content", "")
                        else:
                            logger.warning(f"Structured output failed after {MAX_STRUCTURED_RETRIES} retries")
                    
                    return raw_content

        except requests.exceptions.Timeout:
            logger.warning(f"Model timeout (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            logger.warning(f"Model error (attempt {attempt + 1}/{max_retries}): {e}")

        if attempt < max_retries - 1:
            time.sleep(2)

    return None


def _parse_response(raw: str, intel: MarketIntelligence) -> TradeDecision:
    """Parse model response into TradeDecision.
    V3: Thinking/Output separation (ispirato da thinking.ts di Claude Code).
    Il tag <think> viene estratto e usato come inner_monologue.
    """
    cleaned = raw.strip()
    thinking_content = ""

    # ── Thinking Separation (pattern da thinking.ts) ──
    # Estrai il contenuto di <think>...</think> come monologue bonus
    think_match = re.search(r'<think>(.*?)</think>', cleaned, re.DOTALL)
    if think_match:
        thinking_content = think_match.group(1).strip()[:500]
        cleaned = cleaned.split("</think>")[-1].strip()

    # Strip markdown fences
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    # Stage 1: Direct JSON parse
    parsed = _try_json_parse(cleaned)
    if parsed:
        decision = _validate_parsed(parsed, intel.asset)
        # Arricchisci con il thinking content se il modello non ha scritto monologue
        if thinking_content and not decision.inner_monologue:
            decision.inner_monologue = thinking_content
        return decision

    # Stage 2: Extract JSON object (supporta nested objects)
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned)
    if match:
        parsed = _try_json_parse(match.group())
        if parsed:
            decision = _validate_parsed(parsed, intel.asset)
            if thinking_content and not decision.inner_monologue:
                decision.inner_monologue = thinking_content
            return decision

    # Stage 3: Legacy text format fallback
    action_match = re.search(r'(?:ACTION|decision)[:\s]*(BUY|HOLD)', cleaned, re.IGNORECASE)
    conf_match = re.search(r'(?:CONFIDENCE|confidence)[:\s]*(\d+)', cleaned, re.IGNORECASE)
    if action_match and conf_match:
        return TradeDecision(
            asset=intel.asset,
            decision=Action.BUY if action_match.group(1).upper() == "BUY" else Action.HOLD,
            confidence=min(100, max(0, int(conf_match.group(1)))),
            thesis=f"Legacy format parse: {cleaned[:60]}",
            inner_monologue=thinking_content or ""
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

    # Monologue
    monologue = _sanitize_str(data.get("inner_monologue", data.get("reflexion", "")), max_len=1000)

    # Lists
    technical_basis = _sanitize_list(data.get("technical_basis", []))
    news_basis = _sanitize_list(data.get("news_basis", []))
    risk_flags = _sanitize_list(data.get("risk_flags", []))

    return TradeDecision(
        asset=asset,
        decision=decision,
        confidence=confidence,
        thesis=thesis,
        inner_monologue=monologue,
        technical_basis=technical_basis,
        news_basis=news_basis,
        risk_flags=risk_flags,
        requires_human_verification="meme" in asset.lower() or "low-cap" in " ".join(risk_flags).lower()
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


def _validate_with_swarm(decision: TradeDecision, intel: MarketIntelligence) -> TradeDecision:
    """Valida una decisione BUY interrogando 3 modelli AI gratuiti via OpenRouter.
    Se almeno 2/3 confermano BUY, la decisione è validata. Altrimenti → HOLD.
    Non-blocking: se OpenRouter è offline, la decisione passa invariata."""
    try:
        from ai.openrouter_client import call_swarm_consensus

        prompt = (
            f"Should I BUY {intel.asset} right now?\n"
            f"Price: {intel.close_price:.2f}, RSI_5m: {intel.rsi_5m:.1f}, "
            f"MACD_5m: {intel.macd_5m:.4f}, Regime: {intel.market_regime}, "
            f"Fear&Greed: {intel.fear_and_greed_value}/100\n"
            f"AI thesis: {decision.thesis}\n"
            f"Answer ONLY 'BUY' or 'HOLD' with a one-line reason."
        )

        messages = [
            {"role": "system", "content": "You are a concise trading analyst. Answer BUY or HOLD with one reason."},
            {"role": "user", "content": prompt}
        ]

        results = call_swarm_consensus(messages, max_models=3, timeout=15)

        if not results:
            logger.debug(f"[{intel.asset}] Swarm unreachable, decision unchanged.")
            return decision

        # Count BUY votes
        buy_votes = 0
        total_votes = len(results)
        for model, response in results.items():
            response_upper = response.upper() if response else ""
            if "BUY" in response_upper:
                buy_votes += 1
            logger.debug(f"[SWARM] {model}: {response[:60] if response else 'N/A'}")

        consensus = buy_votes >= 2  # At least 2/3 agree

        if consensus:
            decision._swarm_validated = True
            # Boost confidence slightly when swarm confirms
            decision.confidence = min(95, decision.confidence + 5)
            decision.thesis += f" [Swarm: {buy_votes}/{total_votes} BUY]"
            logger.info(f"[{intel.asset}] ✅ Swarm Consensus: {buy_votes}/{total_votes} BUY → CONFIRMED")
        else:
            # Degrade to HOLD if swarm disagrees
            old_conf = decision.confidence
            decision.decision = Action.HOLD
            decision.confidence = 30
            decision.thesis = f"Swarm rejected ({buy_votes}/{total_votes} BUY). Original conf: {old_conf}%"
            decision.risk_flags.append("swarm_rejection")
            logger.warning(f"[{intel.asset}] ⚠️ Swarm Rejection: {buy_votes}/{total_votes} BUY → DOWNGRADED TO HOLD")

        return decision
    except ImportError:
        logger.debug("OpenRouter client not available. Swarm validation skipped.")
        return decision
    except Exception as e:
        logger.error(f"Swarm validation error (non-critical): {e}")
        return decision

