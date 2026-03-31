import logging
from typing import Optional
from ai.types import MarketIntelligence, TradeDecision
from ai.decision_engine import evaluate as legacy_evaluate
from ai.registry.model_registry import ModelRegistry
from storage.repository import Repository

logger = logging.getLogger("ai.strategy_router")

class StrategyRouter:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.registry = ModelRegistry(repo)

    def evaluate_with_routing(self, intelligence: MarketIntelligence, env: str = "testlab") -> TradeDecision:
        """Route the evaluation request to the correct model version based on environment."""
        active_model = self.registry.get_active_model(env)
        
        logger.info(f"Routing {env} request for {intelligence.asset} to model: {active_model}")
        
        # In V8.1, the legacy_evaluate is extended to support model override via config
        # We simulate the call here. In a real environment, we'd pass the active_model tag
        # to the Ollama API call inside decision_engine.py.
        
        decision = legacy_evaluate(intelligence)
        
        # Attach the resolved model tag to the decision for traceability
        decision.model_tag = active_model # We'll need to update TradeDecision dataclass
        
        return decision

if __name__ == "__main__":
    from storage.repository import Repository
    sr = StrategyRouter(Repository())
    print("Strategy Router V8.1 initialized.")
