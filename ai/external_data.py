"""
EXTERNAL DATA PROVIDER V8.3
Fetches real-time market sentiment and funding data.
"""
import requests
import logging
from typing import Dict, Optional

logger = logging.getLogger("ai.external_data")

class ExternalDataProvider:
    @staticmethod
    def get_fear_greed() -> int:
        """Fetch Fear & Greed Index from alternative.me (0-100)."""
        try:
            resp = requests.get("https://api.alternative.me/fng/", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                val = int(data['data'][0]['value'])
                logger.info(f"Fear & Greed Index: {val}")
                return val
        except Exception as e:
            logger.warning(f"Failed to fetch Fear & Greed: {e}")
        return 50 # Neutral fallback

    @staticmethod
    def get_binance_funding(symbol: str = "BTCUSDT") -> float:
        """Fetch latest funding rate from Binance Futures API."""
        try:
            # Public Fapi endpoint
            resp = requests.get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                rate = float(data[0]['fundingRate'])
                logger.info(f"Funding Rate [{symbol}]: {rate:.6f}")
                return rate
        except Exception as e:
            logger.warning(f"Failed to fetch Funding Rate: {e}")
        return 0.01 # Baseline fallback

    @classmethod
    def get_global_context(cls) -> Dict:
        """Return aggregated external context."""
        return {
            "fear_greed": cls.get_fear_greed(),
            "avg_funding": cls.get_binance_funding()
        }
