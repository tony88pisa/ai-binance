import time
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import Repository
from services.equity_provider import EquityProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EQUITY_DAEMON] %(message)s")
logger = logging.getLogger("equity_daemon")

def run_equity_daemon():
    logger.info("Avvio del Demone Azionario (YFinance Fetcher)...")
    repo = Repository()
    ep = EquityProvider()
    
    while True:
        try:
            assets = ep.get_market_list("ALL")
            logger.info(f"Scaricamento snapshot per {len(assets)} titoli internazionali...")
            
            for ticker in assets:
                # Piccolo delay per non farsi bannare l'IP da Yahoo
                time.sleep(1)
                
                df = ep.get_ohlcv(ticker, timeframe="5m", limit=20)
                if df.empty:
                    continue
                
                # Calcolo metriche basic (es. RSI semplice)
                # Nel mondo reale si usa panda-ta, qui mettiamo dummy data per far lavorare il decisore
                last_price = float(df.iloc[-1]['close'])
                
                data = {
                    "asset": ticker,
                    "price": last_price,
                    "rsi_5m": 50.0, # Dummy fallback if pandas-ta missing
                    "rsi_1h": 50.0,
                    "macd_5m": 0.0,
                    "macd_1h": 0.0,
                    "atr_5m": last_price * 0.01,
                    "decision": "hold",
                    "confidence": 0,
                    "regime": "NORMAL",
                    "consensus_score": 0.0,
                    "position_size_pct": 0.0,
                    "atr_stop_distance": last_price * 0.02,
                    "why_not_trade": ""
                }
                
                repo.upsert_market_snapshot(data)
                
            logger.info("Snapshots inseriti nel database globale.")
        except Exception as e:
            logger.error(f"Errore nel fetcher azionario: {e}")
            
        # Aggiorna ogni 5 minuti (come Freqtrade)
        time.sleep(300)

if __name__ == "__main__":
    run_equity_daemon()
