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
        "rules": "tengu-rules",
    }

    def __init__(self):
        self.local_file = os.path.join(os.path.dirname(__file__), "local_superbrain.json")
        self.local_memories = []
        if os.path.exists(self.local_file):
            try:
                with open(self.local_file, "r", encoding="utf-8") as f:
                    self.local_memories = json.load(f)
            except Exception:
                pass

        api_key = os.getenv("SUPERMEMORY_API_KEY", "").strip()
        if Supermemory and api_key and api_key.startswith("sm_"):
            self.client = Supermemory(api_key=api_key)
            self.cloud_active = True
            self.enabled = True
            logger.info("🧠 SuperBrain inizializzato (Supermemory Cloud attivo).")
        else:
            self.client = None
            self.cloud_active = False
            self.enabled = True # Always enabled due to local fallback
            logger.warning("⚠️ SuperBrain Cloud offline (API Key assente). Fallback su file locale attivo.")

    def _save_local(self):
        try:
            with open(self.local_file, "w", encoding="utf-8") as f:
                json.dump(self.local_memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Errore al salvataggio locale di SuperBrain: {e}")

    def remember(self, category: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """Salva un ricordo in Supermemory e/o nel fallback locale."""
        if not self.enabled:
            return False

        container = self.CONTAINERS.get(category, f"tengu-{category}")
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build payload con metadata strutturato
        payload = f"[{timestamp}] [Category: {category}]\n{content}"
        if metadata:
            payload += f"\n\nMetadata: {json.dumps(metadata, ensure_ascii=False)}"

        if self.cloud_active:
            try:
                self.client.add(content=payload, container_tags=[container])
                logger.debug(f"Ricordo salvato cloud ({category}): {content[:80]}...")
            except Exception as e:
                logger.error(f"SuperBrain.remember failed cloud ({container}): {e}")
        
        # Local fallback execution
        self.local_memories.append({
            "category": category,
            "container": container,
            "timestamp": timestamp,
            "content": content,
            "payload": payload,
            "metadata": metadata or {}
        })
        if len(self.local_memories) > 1000:
            self.local_memories = self.local_memories[-1000:]
        self._save_local()
        return True

    def recall(self, query: str, category: Optional[str] = None, limit: int = 5) -> List[str]:
        """Ricerca semantica nella memoria. Ritorna lista di ricordi rilevanti."""
        if not self.enabled:
            return []

        if not self.cloud_active:
            # LOCAL FALLBACK
            results = sorted(self.local_memories, key=lambda x: x["timestamp"], reverse=True)
            if category:
                results = [r for r in results if r["category"] == category]
            
            query_lower = query.lower()
            matching = [r for r in results if query_lower in r["payload"].lower()]
            if not matching:
                matching = results
                
            return [str(r["payload"])[:500] for r in matching[:limit]]

        # CLOUD RECALL
        try:
            container = self.CONTAINERS.get(category, f"tengu-{category}") if category else None
            if container:
                response = self.client.search.documents(q=query, container_tags=[container])
            else:
                response = self.client.search.documents(q=query)
                
            memories = []
            if hasattr(response, "results"):
                for r in response.results:
                    if hasattr(r, "content"):
                        memories.append(str(r.content)[:500])
                    elif isinstance(r, dict):
                        memories.append(str(r.get("content", r.get("memory", r)))[:500])
                    else:
                        memories.append(str(r)[:500])
                        
            return memories[:limit]
        except Exception as e:
            logger.error(f"SuperBrain.recall failed cloud: {e}")
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

    def remember_rule(self, rule_text: str) -> bool:
        """Salva una Regola d'Oro distillata dagli errori passati."""
        return self.remember("rules", rule_text, {"type": "golden_rule"})

    def get_core_rules(self) -> str:
        """Recupera le Regole d'Oro per non ripetere gli errori vecchi."""
        return self.recall_context("golden rules, do not repeat mistakes, core directives", "rules", limit=5)

    def demote_rules_for_asset(self, asset: str) -> bool:
        """Marca un asset o una regola come obsoleta/non performante (Jewel: Auto-Purge)."""
        logger.info(f"🧠 SuperBrain: Demoting rules for {asset} due to low win-rate.")
        return self.remember_rule(f"!!! BLACKLIST/CRITICAL: {asset} has <45% WR. Avoid trading until strategy is revised on this asset.")

    def compact_index(self, max_lines: int = 20) -> bool:
        """Simula la compattazione dell'indice (Jewel: Context Window Management).
        In Supermemory Cloud, questo si riflette nell'uso di scadenze o priorità nei recall future.
        """
        logger.info(f"🧠 SuperBrain: Index compaction (max {max_lines} lines) requested.")
        # In cloud mode, limitiamo semplicemente i recall futuri o filtriamo per timestamp
        return True


# Singleton
_instance: Optional[SuperBrain] = None

def get_superbrain() -> SuperBrain:
    global _instance
    if _instance is None:
        _instance = SuperBrain()
    return _instance
