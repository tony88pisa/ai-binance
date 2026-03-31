"""
Inference Cache for CACHED validation mode.

Keys model outputs by a deterministic hash of the MarketIntelligence context.
Allows backtesting and replay without melting the GPU.
"""
import hashlib
import json
import logging
from typing import Optional

from ai.types import MarketIntelligence, TradeDecision
from config.settings import get_settings

logger = logging.getLogger("ai.cache")

def _generate_context_hash(intel: MarketIntelligence) -> str:
    """Generate a deterministic hash from the intelligence snapshot."""
    settings = get_settings()
    
    # Bucketize floating points to reduce noise collisions
    # But include enough distinct values to prevent material context merging
    core_context = {
        "asset": intel.asset,
        "timeframe": "5m", # Strategy base timeframe
        "close_price": round(intel.close_price, 2),
        "rsi_5m": round(intel.rsi_5m, 1),
        "macd_5m": round(intel.macd_5m, 4),
        "rsi_1h": round(intel.rsi_1h, 1),
        "macd_1h": round(intel.macd_1h, 4),
        "regime": intel.market_regime,
        "fgi_bucket": intel.fear_and_greed_value // 10, # bucket into deciles
        "sentiment": round(intel.news_sentiment_score, 1),
        "news_count": intel.news_count,
        "staleness_bucket": intel.research_staleness_seconds // 300, # 5 min buckets
        "model": settings.model.model_name,
    }
    context_str = json.dumps(core_context, sort_keys=True)
    return hashlib.sha256(context_str.encode("utf-8")).hexdigest()[:24]

def get_cached_decision(intel: MarketIntelligence) -> Optional[TradeDecision]:
    """Retrieve a previously generated TradeDecision from cache."""
    settings = get_settings()
    cache_path = settings.paths.inference_cache_file
    
    if not cache_path.exists():
        return None
        
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
            
        ctx_hash = _generate_context_hash(intel)
        if ctx_hash in cache:
            data = cache[ctx_hash]
            # Convert dict back to TradeDecision
            from ai.types import Action, DataQuality
            decision = TradeDecision(
                asset=data["asset"],
                decision=Action.BUY if data["decision"] == "buy" else Action.HOLD,
                confidence=data["confidence"],
                thesis=data["thesis"],
                technical_basis=data.get("technical_basis", []),
                news_basis=data.get("news_basis", []),
                risk_flags=data.get("risk_flags", []),
            )
            return decision
    except Exception as e:
        logger.error(f"Failed to read inference cache: {e}")
        
    return None

def save_decision_to_cache(intel: MarketIntelligence, decision: TradeDecision) -> None:
    """Save a successfully generated real TradeDecision to cache."""
    settings = get_settings()
    cache_path = settings.paths.inference_cache_file
    
    try:
        cache = {}
        if cache_path.exists():
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
                
        ctx_hash = _generate_context_hash(intel)
        cache[ctx_hash] = decision.to_dict()
        
        # Write atomically or simply
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write inference cache: {e}")
