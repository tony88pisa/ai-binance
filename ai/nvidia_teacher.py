from typing import Dict, Any
import logging
from ai.nvidia_client import NvidiaClient

logger = logging.getLogger("ai.nvidia_teacher")

class NvidiaTeacher:
    def __init__(self, repo):
        self.repo = repo
        self.client = NvidiaClient()

    def analyze(self) -> Dict[str, Any]:
        """
        Gathers recent outcomes and snapshots, sends them to NVIDIA Cloud,
        and returns actual strategy constraints/overrides elaborated by the LLM.
        """
        outcomes = self.repo.get_recent_outcomes(days=14)
        
        findings = []
        status = "insufficient_data"
        true_max_dd = 0.0
        
        if not outcomes:
            logger.info("Non ci sono trade chiusi, richiedo analisi esplorativa a NVIDIA.")
            snapshots = self.repo.get_latest_snapshots()
            if not snapshots:
                return {"findings": [], "max_drawdown": 0.0, "status": "no_data"}
            
            # Formattiamo i dati di snapshot per darli in pasto all'LLM e dedurre le regole
            trade_data = {"type": "exploratory", "snapshots": [
                 {k: v for k, v in s.items() if k in ("asset", "price", "rsi_5m", "macd_5m", "regime")}
                 for s in snapshots[:15]
            ]}
        else:
            # Abbiamo trade reali, mandiamo lo storico performance a NVIDIA
            trade_data = {"type": "review", "outcomes": [
                {
                    "asset": o.get("asset", "UNK"),
                    "pnl_pct": o.get("realized_pnl_pct", 0.0),
                    "open": o.get("open_at"),
                    "close": o.get("closed_at")
                } for o in outcomes[-20:] # Limitiamo ai 20 più recenti
            ]}
            
            # Calcolo drawdown (locale base)
            equity, peak = 1.0, 1.0
            for o in sorted(outcomes, key=lambda x: x.get("closed_at", "")):
                pnl = o.get("realized_pnl_pct", 0.0) / 100.0
                equity *= (1.0 + pnl)
                if equity > peak: peak = equity
                dd = (equity - peak) / peak
                if dd < true_max_dd: true_max_dd = dd

        # Invocazione reale dell'API NVIDIA
        logger.info("Chiamata al Cloud NVIDIA per valutazione strategica...")
        llm_response = self.client.review_closed_trades([trade_data])
        
        if llm_response:
            # Se l'LLM restituisce un array invece di un singolo oggetto, prendiamo il primo elemento
            if isinstance(llm_response, list) and len(llm_response) > 0:
                llm_response = llm_response[0]
            elif not isinstance(llm_response, dict):
                llm_response = {}

            # Estraiamo i suggerimenti JSON che l'LLM ha creato (candidate_strategies, risk_notes)
            new_rules = llm_response.get("rule_corrections", [])
            strategies = llm_response.get("candidate_strategies", {})
            risk_notes = llm_response.get("risk_notes", "Nessuna nota di rischio specifica.")
            
            # Adattiamo l'output LLM al nostro formato finding
            for rule in new_rules:
                findings.append({
                    "issue": "NVIDIA Insight",
                    "suggested_regime": strategies.get("regime", "general"),
                    "edge": rule,
                    "ai_assessment": risk_notes,
                    "suggested_controls": {
                        "min_confidence": strategies.get("suggested_min_confidence", 75),
                        "max_open_trades": strategies.get("suggested_max_trades", 3),
                        "close_losers_threshold": strategies.get("suggested_stop_loss", -4.0)
                    }
                })
            status = "completed"
        else:
            logger.error("Nessuna risposta valida da NVIDIA API.")
            status = "api_error"

        return {
            "findings": findings,
            "max_drawdown": true_max_dd,
            "status": status
        }
