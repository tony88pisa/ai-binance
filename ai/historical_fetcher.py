import requests
import json
import logging
from pathlib import Path
from datetime import datetime
import time

logger = logging.getLogger("ai.historical_fetcher")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "tmp" / "datasets"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def fetch_klines(symbol: str, interval: str = "5m", limit: int = 1000, max_pages: int = 2) -> list:
    """
    Scarica le kline storiche da Binance API. Usa max_pages per andare indietro nel tempo.
    Ritorna una lista concatenata di kline ordinata cronologicamente (ASC).
    limit max = 1000 per Binance.
    """
    all_klines = []
    end_time = None
    
    # Binance endpoint
    url = "https://api.binance.com/api/v3/klines"
    
    for i in range(max_pages):
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if end_time:
            params["endTime"] = end_time - 1

        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            
            if not data:
                break
                
            # data è [ [open_time, open, high, low, close, volume, close_time, ...], ... ]
            all_klines = data + all_klines
            end_time = data[0][0]  # The oldest open_time in this batch
            
            # Rate limiting safe sleep
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Errore download klines per {symbol}: {e}")
            break
            
    return all_klines

def get_cached_dataset(symbol: str, interval: str = "5m", force_update: bool = False) -> list:
    """Restituisce il dataset dal disco se recente, altrimenti lo scarica."""
    sanitized_sym = symbol.replace("/", "").upper()
    cache_file = DATA_DIR / f"{sanitized_sym}_{interval}_recent.json"
    
    # Se il file esiste da meno di 6 ore, usiamo la cache per evitare ban
    if cache_file.exists() and not force_update:
        if (time.time() - cache_file.stat().st_mtime) < 21600:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
                
    logger.info(f"Scaricamento nuovo dataset storico per {sanitized_sym} ({interval})...")
    # Facciamo limit=1000 con max_pages=3 per avere le ultime 3000 candele (circa 10 giorni a 5m)
    klines = fetch_klines(sanitized_sym, interval=interval, limit=1000, max_pages=3)
    
    if klines:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(klines, f)
            
    return klines

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Historical Fetcher...")
    klines = get_cached_dataset("BTCUSDT", "5m")
    print(f"Downloaded {len(klines)} 5m candles. Oldest: {datetime.fromtimestamp(klines[0][0]/1000)}, Newest: {datetime.fromtimestamp(klines[-1][0]/1000)}")
