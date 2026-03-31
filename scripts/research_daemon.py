import time
import json
import random
import logging
from datetime import datetime, timezone
import sys
import os

# Add parent path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.repository import Repository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - RE_BRAIN - %(levelname)s - %(message)s")
logger = logging.getLogger("research_brain")

class ResearchDaemon:
    def __init__(self):
        self.repo = Repository()
        
    def collect_macro_snapshot(self):
        """Simula la raccolta di dati macro/sentiment (Fear & Greed, API esterne)."""
        # In a real scenario, this fetches from APIs like Alternative.me, CoinGecko, etc.
        fng_score = random.randint(30, 80)
        overall_sentiment = "BULLISH" if fng_score >= 55 else ("BEARISH" if fng_score <= 45 else "NEUTRAL")
        
        # Simulated news impact logic
        news_events = ["SEC ETF updates", "CPI Data Release", "Major Exchange Outage", "DEX Volume Surge"]
        active_event = random.choice(news_events) if random.random() > 0.5 else "Nessun evento rilevante"
        impact_score = random.uniform(-1.0, 1.0) if active_event != "Nessun evento rilevante" else 0.0
        
        sys_risk = "ALTO" if impact_score < -0.5 else ("BASSO" if impact_score > 0.5 else "MEDIO")
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "macro_sentiment": overall_sentiment,
            "fng_index": fng_score,
            "systemic_risk": sys_risk,
            "news_impact": active_event,
            "top_insight": f"Attenzione focalizzata su asset ad alta correlazione con {overall_sentiment.lower()} mode."
        }
        
    def save_snapshot(self, snapshot):
        """Salva in modo atomico su service_state."""
        with self.repo._get_connection() as conn:
            conn.execute(
                "INSERT INTO service_state (service_name, status, last_heartbeat, config_json) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(service_name) DO UPDATE SET "
                "status = excluded.status, "
                "last_heartbeat = excluded.last_heartbeat, "
                "config_json = excluded.config_json",
                ("research_brain", "active", datetime.now(timezone.utc).isoformat(), json.dumps(snapshot))
            )
            conn.commit()

    def run_cycle(self):
        logger.info("Avviato ciclo di raccolta Research Brain (Module 11)...")
        snapshot = self.collect_macro_snapshot()
        self.save_snapshot(snapshot)
        logger.info(f"Ricerca Macro completata: Sentiment={snapshot['macro_sentiment']}, Rischio={snapshot['systemic_risk']}")
        return snapshot

if __name__ == "__main__":
    daemon = ResearchDaemon()
    daemon.run_cycle()
