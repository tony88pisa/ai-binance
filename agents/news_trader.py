import time
import logging
import sys
from pathlib import Path
import schedule

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.news_provider import NewsProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [NEWS_TRADER] %(message)s")
logger = logging.getLogger("news_trader")

def job_scan_news():
    try:
        provider = NewsProvider()
        headlines = provider.get_latest_headlines(limit=3)
        
        # Parole chiave primitive. Nel 2026 qui si collega la fetch a Qwen/DeepSeek per l'analisi del sentimento VERO.
        bullish_keywords = ["surge", "bull", "approval", "jump", "record", "adopt", "buy", "integrates", "partnership"]
        bearish_keywords = ["crash", "hack", "drop", "ban", "lawsuit", "sell", "plunge", "sec", "hacked"]
        
        if headlines:
            logger.info(f"Aggregando {len(headlines)} breaking news dal mondo Cripto/Finanza...")
        
        for h in headlines:
            title_lower = h['title'].lower()
            
            is_bullish = any(w in title_lower for w in bullish_keywords)
            is_bearish = any(w in title_lower for w in bearish_keywords)
            
            if is_bullish:
                logger.info(f"🚨 ALERT FLASH BUY: '{h['title'][:80]}...' -> Calcolato momentum POSITIVO.")
            elif is_bearish:
                logger.info(f"🚨 ALERT FLASH SHORT: '{h['title'][:80]}...' -> Calcolato momentum NEGATIVO.")
                
    except Exception as e:
        logger.error(f"Errore nello scan delle notizie: {e}")

if __name__ == "__main__":
    logger.info("Avvio Event-Driven News Trader Agent (Sentiment Engine)...")
    # Gira ogni 15 minuti per risparmiare API e CPU (come richiesto al MasterPlan)
    schedule.every(15).minutes.do(job_scan_news)
    
    job_scan_news()
    
    while True:
        schedule.run_pending()
        time.sleep(1)
