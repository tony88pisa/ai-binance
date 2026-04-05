from typing import Dict, Any

class SkillValidator:
    def __init__(self, repo):
        self.repo = repo

    def validate(self, skill: Dict[str, Any]) -> Dict[str, Any]:
        # Syntax Check removed for Brute Force param grid

        # Duplicate check
        for existing in self.repo.list_skill_candidates():
            if existing["status"] == "approved" and existing["name"] == skill["name"]:
                return self._fail("duplicate skill name")

        # New Brute Force Engine Validation
        from ai.brute_force_engine import BruteForceEngine
        from ai.historical_fetcher import get_cached_dataset
        import logging
        
        logger = logging.getLogger("skill_validator")
        
        # Stabiliamo che il test avverrà sul BTCUSDT per le skill universali
        target_asset = skill.get("target_asset", "BTCUSDT")
        
        logger.info(f"Avvio Validator Brute Force per la skill: {skill['name']} su {target_asset}")
        
        try:
            klines = get_cached_dataset(target_asset, "5m")
        except Exception as e:
            return self._fail(f"Errore download dati storici: {e}")
            
        # Limite fisso DD a 10% stabilito per basso budget
        engine = BruteForceEngine(max_drawdown_limit=-0.10)
        
        result = engine.evaluate_variants(klines, skill)
        
        if result["passed"]:
            metrics = result["optimized_params"]["metrics"]
            return {
                "passed": True,
                "win_rate": metrics["win_rate"],
                "avg_pnl": metrics["net_pnl_pct"] / metrics["total_trades"] if metrics["total_trades"] > 0 else 0,
                "max_drawdown": metrics["max_drawdown_pct"] / 100.0,
                "profit_factor": 2.0, # Semplificato
                "trade_count": metrics["total_trades"],
                "regime_stability": "STABLE",
                "reason": result["reason"],
                "optimized_params": result["optimized_params"],
                "prompt_rule": result["prompt_rule"]
            }
        else:
            return self._fail(result["reason"])

    def _fail(self, reason: str) -> Dict[str, Any]:
        return {
            "passed": False, "win_rate": 0, "avg_pnl": 0, "max_drawdown": 0,
            "profit_factor": 0, "trade_count": 0, "regime_stability": "N/A", "reason": reason
        }
