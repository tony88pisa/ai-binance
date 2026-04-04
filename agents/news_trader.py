import time
import json
import logging
import schedule
import requests
from datetime import datetime, timezone
import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import Repository
from config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [NEWS_TRADER] %(message)s")
logger = logging.getLogger("news_trader")

settings = get_settings()

class NewsTrader:
    def __init__(self):
        self.repo = Repository()
        self.ollama_url = "http://127.0.0.1:11434/api/chat"
        self.model = "llama3.2:latest"  # Il nuovo modello 3B leggero appena scaricato!
        
    def _get_mock_news(self):
        # In un setup live questo chiama l'API RSS di Yahoo Finance o ForexFactory
        return [
            {"asset": "BABA", "headline": "Alibaba reports stronger than expected earnings in cloud division", "source": "Yahoo Finance"},
            {"asset": "NVDA", "headline": "NVIDIA announces delay in next generation Blackwell chips", "source": "Bloomberg"},
            {"asset": "BTC", "headline": "Fed cuts rates by 50 basis points, risk-on assets rally", "source": "CoinDesk"}
        ]
        
    def analyze_sentiment(self):
        logger.info("Avvio analisi macro-economica e sentiment...")
        news_items = self._get_mock_news()
        
        for item in news_items:
            prompt = f"Analyze this financial news headline: '{item['headline']}'. Is the sentiment for asset {item['asset']} POSITIVE, NEGATIVE, or NEUTRAL? Answer only with ONE WORD."
            
            try:
                r = requests.post(self.ollama_url, json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                }, timeout=30)
                
                if r.status_code == 200:
                    response_text = r.json().get("response", "").strip().upper()
                    
                    if "POSITIVE" in response_text:
                        score = 1.0
                    elif "NEGATIVE" in response_text:
                        score = -1.0
                    else:
                        score = 0.0
                        
                    logger.info(f"[{item['asset']}] Sentiment: {response_text} (Score: {score})")
                    
                    # Log to live activity feed
                    self.repo.log_activity("news_trader", "SENTIMENT", f"{item['asset']}: {response_text} — {item['headline'][:60]}...")
                    
                    # Salva il finding nel database per la Squadra Equity e Crypto
                    skill = {
                        "skill_id": f"SNT-{item['asset']}-{int(time.time())}",
                        "name": f"sentiment_{item['asset'].lower()}",
                        "version": "1.0.0",
                        "validation_status": "active",  # News is direct factor
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "logic": f"News Sentiment {response_text}: {item['headline']}"
                    }
                    self.repo.save_skill_candidate(skill)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Errore connessione Ollama ({self.model}): {e}")
                
        # Heartbeat
        self.repo.update_service_heartbeat("news_trader", json.dumps({
            "mode": "ACTIVE", "last_run": datetime.now(timezone.utc).isoformat()
        }))

def run_job():
    trader = NewsTrader()
    trader.analyze_sentiment()

if __name__ == "__main__":
    logger.info("News Trader Agent (Llama 3.2 3B) Init...")
    schedule.every(30).minutes.do(run_job)
    run_job()
    
    while True:
        schedule.run_pending()
        time.sleep(1)
