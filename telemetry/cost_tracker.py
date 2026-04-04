"""
Cost Tracker — Tracks AI API usage (tokens, cost, duration) per model.

Inspired by src/cost-tracker.ts from the Claude Code agent framework.
Provides per-session and cumulative tracking with JSON persistence.
"""
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger("telemetry.cost_tracker")

# Pricing per 1M tokens (approximate for common models)
MODEL_PRICING = {
    # NVIDIA NIM (Llama 3.1 70B via integrate.api.nvidia.com)
    "meta/llama-3.1-70b-instruct": {"input": 0.35, "output": 0.40},
    "meta/llama-3.3-70b-instruct": {"input": 0.35, "output": 0.40},
    # Local Ollama (free, but track tokens for context window management)
    "qwen3:8b": {"input": 0.0, "output": 0.0},
    "qwen2.5-coder:7b": {"input": 0.0, "output": 0.0},
    # Fallback
    "default": {"input": 0.50, "output": 0.60},
}


@dataclass
class APICallRecord:
    timestamp: str
    model: str
    caller: str  # "decision_engine", "risk_controller", "evolution_loop"
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    cost_usd: float = 0.0
    success: bool = True
    error: Optional[str] = None


@dataclass 
class SessionCosts:
    session_start: str = ""
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    calls_by_model: dict = field(default_factory=dict)
    calls_by_caller: dict = field(default_factory=dict)
    recent_calls: list = field(default_factory=list)  # Last 50 calls


class CostTracker:
    """Singleton-style cost tracker with JSON persistence."""
    
    MAX_RECENT_CALLS = 50
    
    def __init__(self, project_root: str):
        self.telemetry_dir = Path(project_root) / "telemetry"
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        self.costs_file = self.telemetry_dir / "api_costs.json"
        self.session = self._load_or_create_session()
    
    def _load_or_create_session(self) -> SessionCosts:
        """Load existing costs or start fresh session."""
        if self.costs_file.exists():
            try:
                with open(self.costs_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session = SessionCosts(**{
                    k: v for k, v in data.items() 
                    if k in SessionCosts.__dataclass_fields__
                })
                return session
            except Exception:
                pass
        
        session = SessionCosts(
            session_start=datetime.now(timezone.utc).isoformat()
        )
        return session
    
    def _save(self):
        """Persist current session costs to disk."""
        try:
            with open(self.costs_file, "w", encoding="utf-8") as f:
                json.dump(asdict(self.session), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cost data: {e}")
    
    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate USD cost for a given API call."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        cost = (input_tokens * pricing["input"] / 1_000_000) + \
               (output_tokens * pricing["output"] / 1_000_000)
        return round(cost, 6)
    
    def record_call(
        self,
        model: str,
        caller: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration_ms: int = 0,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """Record a single API call with its metrics."""
        cost = self._calculate_cost(model, input_tokens, output_tokens)
        
        record = APICallRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            caller=caller,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            cost_usd=cost,
            success=success,
            error=error,
        )
        
        # Update session totals
        self.session.total_calls += 1
        self.session.total_input_tokens += input_tokens
        self.session.total_output_tokens += output_tokens
        self.session.total_cost_usd = round(self.session.total_cost_usd + cost, 6)
        self.session.total_duration_ms += duration_ms
        
        # Update per-model breakdown
        if model not in self.session.calls_by_model:
            self.session.calls_by_model[model] = {
                "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0
            }
        m = self.session.calls_by_model[model]
        m["calls"] += 1
        m["input_tokens"] += input_tokens
        m["output_tokens"] += output_tokens
        m["cost_usd"] = round(m["cost_usd"] + cost, 6)
        
        # Update per-caller breakdown
        if caller not in self.session.calls_by_caller:
            self.session.calls_by_caller[caller] = {
                "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0
            }
        c = self.session.calls_by_caller[caller]
        c["calls"] += 1
        c["input_tokens"] += input_tokens
        c["output_tokens"] += output_tokens
        c["cost_usd"] = round(c["cost_usd"] + cost, 6)
        
        # Maintain recent calls ring buffer
        self.session.recent_calls.append(asdict(record))
        if len(self.session.recent_calls) > self.MAX_RECENT_CALLS:
            self.session.recent_calls = self.session.recent_calls[-self.MAX_RECENT_CALLS:]
        
        # Persist
        self._save()
        
        logger.debug(
            f"[COST] {caller} → {model}: "
            f"{input_tokens}in/{output_tokens}out = ${cost:.6f} "
            f"({duration_ms}ms) Total: ${self.session.total_cost_usd:.4f}"
        )
    
    def get_summary(self) -> dict:
        """Get a summary of all costs for dashboard/MCP display."""
        return {
            "session_start": self.session.session_start,
            "total_calls": self.session.total_calls,
            "total_tokens": {
                "input": self.session.total_input_tokens,
                "output": self.session.total_output_tokens,
                "total": self.session.total_input_tokens + self.session.total_output_tokens,
            },
            "total_cost_usd": self.session.total_cost_usd,
            "total_duration_ms": self.session.total_duration_ms,
            "by_model": self.session.calls_by_model,
            "by_caller": self.session.calls_by_caller,
            "recent_calls_count": len(self.session.recent_calls),
        }
    
    def reset(self):
        """Reset all costs (e.g., daily reset)."""
        self.session = SessionCosts(
            session_start=datetime.now(timezone.utc).isoformat()
        )
        self._save()


# Module-level singleton
_tracker: Optional[CostTracker] = None

def get_cost_tracker(project_root: str = ".") -> CostTracker:
    """Get or create the global CostTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker(project_root)
    return _tracker
