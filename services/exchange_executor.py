import os
import logging
from dotenv import load_dotenv
from binance.client import Client
from binance.enums import *
from typing import Dict, Any, Optional

# Ensure .env is loaded
load_dotenv()

logger = logging.getLogger("exchange_executor")

class ExchangeExecutor:
    """Handles real-time exchange execution for Binance (Testnet or Live)."""
    
    def __init__(self):
        # Load .env from project root
        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / ".env"
        load_dotenv(dotenv_path=env_path)
        
        self.mode = os.getenv("EXCHANGE_MODE", "testnet").lower()
        self.api_key = os.getenv("BINANCE_TESTNET_API_KEY", "").strip()
        self.api_secret = os.getenv("BINANCE_TESTNET_SECRET", "").strip()
        
        self.client: Optional[Client] = None
        self.enabled = False
        
        if not self.api_key or self.api_key == "PASTE_HERE":
            logger.warning(f"[EXCHANGE] API Keys missing or default in {env_path}. Executor DISABLED.")
            return
            
        try:
            # Masked logging for debugging
            key_preview = self.api_key[:4] + "..." if self.api_key else "None"
            logger.info(f"[EXCHANGE] Initializing {self.mode.upper()} mode with Key: {key_preview}")
            
            testnet = (self.mode == "testnet")
            self.client = Client(self.api_key, self.api_secret, testnet=testnet)
            
            # Useping for connectivity check instead of system status
            self.client.ping()
            self.enabled = True
            logger.info(f"[EXCHANGE] {self.mode.upper()} connected successfully.")
        except Exception as e:
            logger.error(f"[EXCHANGE] Initialization failed: {e}")
            self.enabled = False

    def _format_symbol(self, symbol: str) -> str:
        """Convert BTC/USDT to BTCUSDT"""
        return symbol.replace("/", "").replace("_", "")

    def get_balance(self, asset: str = "USDT") -> float:
        """Get the free balance of a specific asset."""
        if not self.enabled or not self.client:
            return 0.0
        try:
            balance = self.client.get_asset_balance(asset=asset)
            return float(balance['free']) if balance else 0.0
        except Exception as e:
            logger.error(f"[EXCHANGE] Failed to get balance for {asset}: {e}")
            return 0.0

    def place_buy_order(self, symbol: str, usdt_amount: float) -> Optional[Dict[str, Any]]:
        """Place a Market BUY order based on USDT amount."""
        if not self.enabled or not self.client:
            logger.info(f"[EXCHANGE] Execution disabled. Simulated BUY for {symbol} not sent to exchange.")
            return None
            
        try:
            formatted_sym = self._format_symbol(symbol)
            logger.info(f"[EXCHANGE] Placing Market BUY for {formatted_sym} with {usdt_amount} USDT...")
            
            # Use create_order for market buy with quoteOrderQty
            order = self.client.create_order(
                symbol=formatted_sym,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quoteOrderQty=round(usdt_amount, 2)
            )
            logger.info(f"[EXCHANGE] BUY order success: {order['orderId']}")
            return order
        except Exception as e:
            logger.error(f"[EXCHANGE] Market BUY order FAILED for {symbol}: {e}")
            return None

    def place_sell_order(self, symbol: str, quantity: float) -> Optional[Dict[str, Any]]:
        """Place a Market SELL order based on asset quantity."""
        if not self.enabled or not self.client:
            logger.info(f"[EXCHANGE] Execution disabled. Simulated SELL for {symbol} not sent to exchange.")
            return None
            
        try:
            formatted_sym = self._format_symbol(symbol)
            logger.info(f"[EXCHANGE] Placing Market SELL for {formatted_sym} with quantity {quantity}...")
            
            # Use create_order for market sell
            # Note: Binance expects float but some assets need specific precision.
            # We use a broad rounding here; in production, you'd check lot_size.
            order = self.client.create_order(
                symbol=formatted_sym,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity 
            )
            logger.info(f"[EXCHANGE] SELL order success: {order['orderId']}")
            return order
        except Exception as e:
            logger.error(f"[EXCHANGE] Market SELL order FAILED for {symbol}: {e}")
            return None

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """List current open orders."""
        if not self.enabled or not self.client:
            return []
        try:
            formatted_sym = self._format_symbol(symbol) if symbol else None
            return self.client.get_open_orders(symbol=formatted_sym)
        except Exception as e:
            logger.error(f"[EXCHANGE] Failed to get open orders: {e}")
            return []

if __name__ == "__main__":
    # Test stub
    logging.basicConfig(level=logging.INFO)
    executor = ExchangeExecutor()
    if executor.enabled:
        print(f"USDT Balance: {executor.get_balance('USDT')}")
