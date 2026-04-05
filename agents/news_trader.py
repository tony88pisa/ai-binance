"""
News Trader V2 — Agente di analisi sentiment basato su notizie REALI.
Usa research/ingester.py per fetch RSS + Fear & Greed Index.
Salva i segnali su SuperBrain (Supermemory) e nel database.
"""
import time
import json
import logging
import schedule
from datetime import datetime, timezone
import os
import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [NEWS_TRADER] %(message)s",
    handlers=[logging.FileHandler(LOGS_DIR / "news_trader.log", encoding='utf-8', delay=True), logging.StreamHandler()]
)
logger = logging.getLogger("news_trader")

from storage.repository import Repository
from storage.superbrain import get_superbrain
from config.settings import get_settings

settings = get_settings()


class NewsTrader:
    def __init__(self):
        self.repo = Repository()
        self.brain = get_superbrain()
        self.seen_hashes: set = set()

    def analyze_sentiment(self):
        """Fetch notizie REALI, analizza sentiment, e salva segnali."""
        logger.info("Avvio analisi sentiment da feed RSS reali...")

        # 1. Fetch news reali dal pipeline ingester
        try:
            from research.ingester import fetch_raw_news, normalize_news, fetch_fear_and_greed

            # Fear & Greed Index
            fng = fetch_fear_and_greed()
            logger.info(f"Fear & Greed Index: {fng.regime.value} (Value: {fng.fear_greed_value})")

            # Salva il segnale macro su SuperBrain
            self.brain.remember_market_signal(
                "GLOBAL",
                f"Fear & Greed Index: {fng.fear_greed_value}/100 ({fng.regime.value})",
                confidence=int(fng.fear_greed_value)
            )

            # Fetch e normalizza le news
            raw_items = fetch_raw_news()
            if not raw_items:
                logger.info("Nessuna notizia recuperata dai feed. Prossimo ciclo tra 15 min.")
                return

            normalized = normalize_news(raw_items, self.seen_hashes)
            logger.info(f"Processate {len(normalized)} notizie ({len(raw_items)} raw, {len(raw_items) - len(normalized)} duplicati rimossi)")

            # 2. Analizza ogni notizia normalizzata
            bullish_count = 0
            bearish_count = 0

            for item in normalized:
                # Log strutturato
                emoji = "📈" if item.sentiment_score > 0.15 else ("📉" if item.sentiment_score < -0.15 else "➡️")
                logger.info(f"{emoji} [{item.sentiment_label.value}] {item.title[:80]}... (score: {item.sentiment_score:+.2f}, urgency: {item.urgency_score:.1f})")

                if item.sentiment_score > 0.15:
                    bullish_count += 1
                elif item.sentiment_score < -0.15:
                    bearish_count += 1

                # 3. Salva su SuperBrain per gli altri agenti
                if abs(item.sentiment_score) > 0.15:  # Solo segnali significativi
                    for asset in item.asset_tags:
                        self.brain.remember_market_signal(
                            asset,
                            f"News Sentiment {item.sentiment_label.value}: {item.title[:100]} (score: {item.sentiment_score:+.2f}, themes: {','.join(item.themes)})",
                            confidence=int(abs(item.sentiment_score) * 100)
                        )

                # 4. Segnali ad alta urgenza → feedback immediato
                if item.urgency_score > 0.7:
                    self.brain.remember_feedback(
                        f"🚨 URGENT NEWS ({item.urgency_score:.1f}): {item.title[:120]} — Sentiment: {item.sentiment_label.value}",
                        agent="news_trader"
                    )
                    logger.warning(f"🚨 ALERT: Notizia urgente rilevata! {item.title[:80]}")

                # 5. Log nel database (per la dashboard)
                try:
                    self.repo.log_activity(
                        "news_trader",
                        "SENTIMENT",
                        f"{','.join(item.asset_tags) or 'MARKET'}: {item.sentiment_label.value} — {item.title[:60]}..."
                    )
                except Exception:
                    pass  # Activity log is best-effort

            # 6. Sommario del ciclo
            total = len(normalized)
            neutral = total - bullish_count - bearish_count
            market_mood = "BULLISH" if bullish_count > bearish_count * 1.5 else (
                "BEARISH" if bearish_count > bullish_count * 1.5 else "NEUTRAL"
            )

            logger.info(f"Sommario: {bullish_count} bullish, {bearish_count} bearish, {neutral} neutral → Mood: {market_mood}")

            # Salva il sommario aggregato su SuperBrain
            self.brain.remember_market_signal(
                "GLOBAL",
                f"News Cycle Summary: {total} news analyzed. {bullish_count} bullish, {bearish_count} bearish. Overall mood: {market_mood}",
                confidence=70
            )

        except ImportError as e:
            logger.error(f"Impossibile importare il pipeline di news: {e}. Controlla che research/ingester.py esista.")
        except Exception as e:
            logger.error(f"Errore durante l'analisi sentiment: {e}", exc_info=True)

        # Heartbeat
        self.repo.update_service_heartbeat("news_trader", json.dumps({
            "mode": "ACTIVE",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "cycle_interval": "15min"
        }))


def run_job():
    trader = NewsTrader()
    trader.analyze_sentiment()


if __name__ == "__main__":
    logger.info("News Trader V2 (Real RSS + Fear & Greed) Init...")
    schedule.every(15).minutes.do(run_job)
    run_job()

    while True:
        schedule.run_pending()
        time.sleep(1)
