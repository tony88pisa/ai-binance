import os
import json
import requests
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("ai.nvidia_client")

class NvidiaClient:
    """
    NVIDIA Teacher Client (Modulo V8.2).
    Integrazione isolata per la revisione post-market delle decisioni AI.
    """
    def __init__(self):
        # Configurazione da Env (Phase 2 spec)
        self.api_key = os.getenv("NVIDIA_API_KEY")
        self.base_url = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
        self.enabled = os.getenv("NVIDIA_ENABLED", "true").lower() == "true"
        
        # Policy & Budget (Phase 8 spec)
        self.max_calls_day = int(os.getenv("NVIDIA_MAX_CALLS_PER_DAY", "3"))
        self.max_tokens_in = int(os.getenv("NVIDIA_MAX_ESTIMATED_INPUT_TOKENS", "12000"))
        self.max_tokens_out = int(os.getenv("NVIDIA_MAX_OUTPUT_TOKENS", "16384"))
        self.hard_stop = os.getenv("NVIDIA_HARD_STOP_ON_BUDGET", "true").lower() == "true"

    def _estimate_tokens(self, text: str) -> int:
        """Stima approssimativa dei token (4 caratteri per token)."""
        return len(text) // 4

    def review_closed_trades(self, trade_data_list: list) -> Optional[Dict[str, Any]]:
        """
        Invia i trade chiusi a NVIDIA per l'analisi degli errori (Layer B/C).
        Non può essere chiamata nel path LIVE.
        """
        if not self.enabled or not self.api_key or self.api_key.lower() == "mock":
            logger.warning("NVIDIA Teacher API Key non valida o in modalità MOCK.")
            return None

        # 1. Preparazione Payload Compatto
        payload_content = json.dumps(trade_data_list, ensure_ascii=False)
        estimated_in = self._estimate_tokens(payload_content)
        
        # 2. Budget Check
        if estimated_in > self.max_tokens_in:
            logger.error(f"Payload troppo grande ({estimated_in} > {self.max_tokens_in}). Blocco sicuro.")
            if self.hard_stop: return None
            # Fallback: summarization locale (PARTIAL)
            payload_content = payload_content[:self.max_tokens_in * 3] # Tronca

        # 3. Chiamata API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = (
            "Sei un assistente trading 'Teacher' (Tengu V11) specializzato in Micro-Capital Scaler (budget 50-100€). "
            "Analizza questi dati. Il bot usa un Grid Trading Engine (per mercati laterali) e un Momentum Engine (per trend). "
            "Identifica fallimenti dominanti, errata confidenza e suggerisci correzioni precise per micro-capitali. "
            "Valuta quale strategia (Grid vs Momentum) sia più adatta al regime corrente. "
            "Rispondi ESCLUSIVAMENTE in JSON con queste chiavi: "
            "reviewed_period, dominant_failures, confidence_miscalibration, regime_findings, recommended_engine, "
            "prompt_corrections, rule_corrections, candidate_strategies, suggested_labels, risk_notes."
        )

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Dati Trade: {payload_content}"}
            ],
            "temperature": 0.1,
            "max_tokens": self.max_tokens_out,
            "stream": False
        }

        try:
            logger.info(f"Chiamata NVIDIA Teacher (Modello: {self.model}). Tokens stimati: {estimated_in}")
            response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=body, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Parsing del JSON di NVIDIA
                try:
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    return json.loads(content[start:end])
                except Exception as e:
                    logger.error(f"Errore parsing risposta NVIDIA: {e}. Raw content: {content}")
                    return None
            else:
                logger.error(f"Errore API NVIDIA ({response.status_code}): {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Eccezione durante chiamata NVIDIA: {e}")
            return None

    def generate_candidate_strategies(self, evidence: dict) -> list:
        """NOT IMPLEMENTED (Placeholder per Phase 2)."""
        return []

    def label_training_examples(self, raw_data: list) -> list:
        """NOT IMPLEMENTED (Placeholder per Phase 2)."""
        return []

if __name__ == "__main__":
    # Test isolato (REAL)
    client = NvidiaClient()
    print(f"NVIDIA Client Inizializzato: Enabled={client.enabled}, Model={client.model}")
