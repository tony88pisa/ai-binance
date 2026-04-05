"""
CCXT Executor — Multi-Exchange Execution Engine per Low-Cap Gems.

A differenza del simulatore, questo handler usa CCXT per operare sui futures
e spot di exchange ad alto rischio/alta volatilità come MEXC, Bybit e KuCoin,
dando sfogo alla Gem Hunter (Agent News Trader).
"""

import ccxt
import logging
from config.settings import get_settings

logger = logging.getLogger("execution.ccxt_executor")

class CCXTExecutor:
    def __init__(self):
        self.settings = get_settings()
        self.exchange_name = self.settings.exchange.name.lower()
        self.mode = self.settings.exchange.mode
        
        # Inizializza dinamicamente l'exchange passato nei config (es: 'mexc' o 'bybit')
        try:
            exchange_class = getattr(ccxt, self.exchange_name)
        except AttributeError:
            logger.error(f"Exchange {self.exchange_name} non supportato da CCXT.")
            exchange_class = ccxt.binance # Fallback
            
        auth = {
            "apiKey": self.settings.exchange.key,
            "secret": self.settings.exchange.secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": "swap" # Per usare i futures di default
            }
        }
        
        if self.mode == "testnet":
            auth["apiKey"] = self.settings.exchange.testnet_key
            auth["secret"] = self.settings.exchange.testnet_secret
            
        self.exchange = exchange_class(auth)
        
        if self.mode == "testnet":
            self.exchange.set_sandbox_mode(True)
            
        logger.info(f"CCXT Executor connesso a {self.exchange_name.upper()} in modalità {self.mode.upper()}")
        
    def get_wallet_balance(self):
        """Restituisce il saldo in USDT dell'account per il compounding sizing."""
        if self.settings.trading.dry_run:
            return 100.00 # Simulated micro-cap
            
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance['total'].get('USDT', 0.0)
            return usdt
        except Exception as e:
            logger.error(f"Errore caricamento bilancio CCXT: {e}")
            return 0.0
            
    def execute_order(self, symbol: str, action: str, size_usdt: float, leverage: int = 10):
        """
        Esegue un ordine usando la libreria CCXT.
        
        Args:
            symbol (str): ES: 'DOGE/USDT'
            action (str): 'buy' o 'sell'
            size_usdt (float): La quota calcolata in USDT (Kelly Criterion Auto-compounding)
            leverage (int): La leva finanziaria (solo se usiamo futures swap)
        """
        if self.settings.trading.dry_run:
            logger.info(f"[DRY-RUN] Eseguirebbe {action.upper()} su {symbol} (Dimensione: {size_usdt} USDT, Leva: {leverage}X)")
            return {"status": "success", "mocked": True}
            
        try:
            # 1. Imposta la leva
            # Su ccxt le API per la leva variano da exchange a exchange, tipicamente:
            if self.exchange.has['setLeverage']:
                self.exchange.set_leverage(leverage, symbol)
                
            # 2. Ottieni il prezzo per calcolare la size del token
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            quantity = (size_usdt * leverage) / current_price
            
            # 3. Esegui a mercato
            order_side = 'buy' if action.lower() == 'buy' else 'sell'
            order = self.exchange.create_market_order(symbol, order_side, quantity)
            
            logger.info(f"Ordine eseguito su {self.exchange_name}: {order_side.upper()} {quantity} {symbol} @ {current_price}")
            return order
            
        except Exception as e:
            logger.error(f"Impossibile eseguire ordine CCXT per {symbol}: {e}")
            return {"status": "failed", "error": str(e)}

    # TODO: Logica stop loss dinamica da implementare nel ciclo di vita
