"""
SuperBrain — Supermemory-First Memory Layer for Tengu V10.
Ogni agente pensa con Supermemory, esegue con SQLite.

Container Tags:
  tengu-strategies  → Strategie tattiche generate dal Dream Agent
  tengu-feedback    → Feedback dal Risk Controller
  tengu-skills      → Skill generate e validate
  tengu-market      → Contesto di mercato e pattern osservati
  tengu-reports     → Report del Coordinator
"""
import os
import json
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger("storage.superbrain")

try:
    from supermemory import Supermemory
except ImportError:
    Supermemory = None


class SuperBrain:
    """Cervello centrale basato su Supermemory con container tag isolati."""

    CONTAINERS = {
        "strategies": "tengu-strategies",
        "feedback": "tengu-feedback",
        "skills": "tengu-skills",
        "market": "tengu-market",
        "reports": "tengu-reports",
    }

    def __init__(self):
        api_key = os.getenv("SUPERMEMORY_API_KEY", "").strip()
        if Supermemory and api_key and api_key.startswith("sm_"):
            self.client = Supermemory(api_key=api_key)
            self.enabled = True
            logger.info("🧠 SuperBrain inizializzato (Supermemory Cloud attivo).")
        else:
            self.client = None
            self.enabled = False
            logger.warning("⚠️ SuperBrain offline (SUPERMEMORY_API_KEY assente).")

    def remember(self, category: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """Salva un ricordo in Supermemory con il container tag corretto."""
        if not self.enabled:
            return False

        container = self.CONTAINERS.get(category, f"tengu-{category}")
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build payload con metadata strutturato
        payload = f"[{timestamp}] [Category: {category}]\n{content}"
        if metadata:
            payload += f"\n\nMetadata: {json.dumps(metadata, ensure_ascii=False)}"

        try:
            self.client.add(content=payload, containerTag=container)
            logger.debug(f"Ricordo salvato in {container}: {content[:80]}...")
            return True
        except Exception as e:
            logger.error(f"SuperBrain.remember failed ({container}): {e}")
            return False

    def recall(self, query: str, category: Optional[str] = None, limit: int = 5) -> List[str]:
        """Ricerca semantica nella memoria. Ritorna lista di ricordi rilevanti."""
        if not self.enabled:
            return []

        try:
            url = "https://api.supermemory.ai/v4/search"
            headers = {
                "Authorization": f"Bearer {self.client.api_key}",
                "Content-Type": "application/json"
            }
            payload = {"q": query, "limit": limit}
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            res.raise_for_status()
            result = res.json()

            memories = []
            if isinstance(result, dict) and "results" in result:
                for r in result["results"]:
                    memories.append(str(r.get("content", r.get("memory", r)))[:500])

            return memories
        except Exception as e:
            logger.error(f"SuperBrain.recall failed: {e}")
            return []

    def recall_context(self, query: str, category: Optional[str] = None, limit: int = 3) -> str:
        """Ritorna un blocco di testo formattato pronto per essere iniettato in un prompt LLM."""
        memories = self.recall(query, category, limit)
        if not memories:
            return ""

        header = f"=== SUPERMEMORY ({category or 'ALL'}) ==="
        lines = [header]
        for i, mem in enumerate(memories, 1):
            lines.append(f"  [{i}] {mem[:400]}")
        lines.append("=" * len(header))
        return "\n".join(lines)

    def remember_strategy(self, strategy_text: str) -> bool:
        """Salva una strategia tattica rolling."""
        return self.remember("strategies", strategy_text, {"type": "tactical_rolling"})

    def remember_feedback(self, feedback: str, agent: str = "unknown") -> bool:
        """Salva un feedback dal Risk Controller o da un alert."""
        return self.remember("feedback", feedback, {"source_agent": agent})

    def remember_skill(self, skill: Dict) -> bool:
        """Salva una skill candidate/approvata."""
        return self.remember("skills", json.dumps(skill, ensure_ascii=False), {"skill_id": skill.get("skill_id")})

    def remember_market_signal(self, asset: str, signal: str, confidence: int = 0) -> bool:
        """Salva un segnale di mercato osservato."""
        return self.remember("market", f"{asset}: {signal}", {"asset": asset, "confidence": confidence})

    def remember_report(self, report: str) -> bool:
        """Salva un report del Coordinator."""
        return self.remember("reports", report, {"type": "coordinator_report"})

    def get_current_strategy(self) -> str:
        """Recupera la strategia tattica corrente."""
        memories = self.recall("current tactical strategy for next 30 minutes", "strategies", limit=1)
        return memories[0] if memories else ""

    def get_recent_feedback(self) -> str:
        """Recupera i feedback recenti per il Dream Agent."""
        return self.recall_context("recent errors, anomalies, risk violations and feedback", "feedback", limit=5)

    def get_market_context(self, asset: str) -> str:
        """Recupera il contesto di mercato per un asset specifico."""
        return self.recall_context(f"trading context, patterns and signals for {asset}", "market", limit=3)


# Singleton
_instance: Optional[SuperBrain] = None

def get_superbrain() -> SuperBrain:
    global _instance
    if _instance is None:
        _instance = SuperBrain()
    return _instance
