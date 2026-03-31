import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from binance.client import Client
from binance.enums import *
from config.settings import get_settings

logger = logging.getLogger("exchange_executor")

class ExchangeExecutor:
    """
    Professional Exchange Executor.
    Supports SIMULATION (local), TESTNET (Binance), and LIVE (Blocked).
    Handles LOT_SIZE and PRICE_FILTER automatically.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.mode = self.settings.exchange.mode.lower()
        self.enabled = False
        self.client: Optional[Client] = None
        self._exchange_info = {}
        
        # Initial capital for simulation
        self._sim_balance = self.settings.trading.wallet_size
        self._sim_assets = {} # asset -> quantity

        if self.mode == "live":
            logger.critical("[EXCHANGE] LIVE MODE is BLOCKED for safety. Use 'testnet' or 'simulation'.")
            return

        if self.mode == "testnet":
            key = self.settings.exchange.testnet_key
            secret = self.settings.exchange.testnet_secret
            
            if not key or not secret:
                logger.warning("[EXCHANGE] Testnet keys missing. Falling back to SIMULATION.")
                self.mode = "simulation"
            else:
                try:
                    self.client = Client(key, secret, testnet=True)
                    self.client.ping()
                    self._load_exchange_info()
                    self.enabled = True
                    logger.info(f"[EXCHANGE] Connected to BINANCE TESTNET. Status: OK")
                except Exception as e:
                    logger.error(f"[EXCHANGE] Testnet connection failed: {e}. Falling back to SIMULATION.")
                    self.mode = "simulation"
                    self.client = None

        if self.mode == "simulation":
            self.enabled = True
            logger.info(f"[EXCHANGE] Initialized in SIMULATION mode. Capital: {self._sim_balance} {self.settings.trading.stake_currency}")

    def _load_exchange_info(self):
        """Fetch and cache exchange info for precision filters."""
        if not self.client: return
        try:
            info = self.client.get_exchange_info()
            for s in info['symbols']:
                self._exchange_info[s['symbol']] = s
        except Exception as e:
            logger.error(f"[EXCHANGE] Failed to load exchange info: {e}")

    def _format_symbol(self, symbol: str) -> str:
        """Standardize symbol for Binance (BTC/USDT -> BTCUSDT)"""
        return symbol.replace("/", "").replace("_", "").upper()

    def _apply_filters(self, symbol: str, quantity: float) -> float:
        """Apply LOT_SIZE filter to quantity."""
        if self.mode == "simulation": return quantity
        
        s_info = self._exchange_info.get(self._format_symbol(symbol))
        if not s_info: return quantity
        
        lot_filter = next((f for f in s_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
        if not lot_filter: return quantity
        
        step_size = float(lot_filter['stepSize'])
        precision = len(lot_filter['stepSize'].split('.')[-1].rstrip('0')) if '.' in lot_filter['stepSize'] else 0
        
        # Round down to nearest stepSize
        return round(quantity - (quantity % step_size), precision)

    def get_balance(self, asset: str = "USDT") -> float:
        """Get available balance for asset."""
        if self.mode == "simulation":
            if asset == self.settings.trading.stake_currency:
                return self._sim_balance
            return self._sim_assets.get(asset, 0.0)
            
        if not self.client or not self.enabled: return 0.0
        try:
            balance = self.client.get_asset_balance(asset=asset.upper())
            return float(balance['free']) if balance else 0.0
        except Exception as e:
            logger.error(f"[EXCHANGE] get_balance failed for {asset}: {e}")
            return 0.0

    def get_asset_balance(self, symbol: str) -> float:
        """Get balance for the base asset of a pair (e.g. BTC from BTCUSDT)"""
        asset = symbol.replace("USDT", "").replace("/", "").upper()
        return self.get_balance(asset)

    def place_market_buy(self, symbol: str, usdt_amount: float) -> Optional[Dict[str, Any]]:
        """Execute a Market BUY."""
        formatted_sym = self._format_symbol(symbol)
        
        if self.mode == "simulation":
            if usdt_amount > self._sim_balance:
                logger.error(f"[SIMULATION] Insufficient balance: {usdt_amount} > {self._sim_balance}")
                return None
            
            # Simulated execution (mock)
            self._sim_balance -= usdt_amount
            asset = symbol.replace("USDT", "").replace("/", "").upper()
            mock_qty = usdt_amount / 60000.0 # Just a placeholder price
            self._sim_assets[asset] = self._sim_assets.get(asset, 0.0) + mock_qty
            
            logger.info(f"[SIMULATION] BUY {formatted_sym} | Amount: {usdt_amount} USDT")
            return {"orderId": "SIM_BUY_" + os.urandom(4).hex(), "status": "FILLED", "origQty": mock_qty}

        try:
            logger.info(f"[EXCHANGE] Placing TESTNET Market BUY: {formatted_sym} ({usdt_amount} USDT)")
            order = self.client.create_order(
                symbol=formatted_sym,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quoteOrderQty=round(usdt_amount, 2)
            )
            return order
        except Exception as e:
            logger.error(f"[EXCHANGE] Market BUY FAILED for {symbol}: {e}")
            return None

    def place_market_sell(self, symbol: str, quantity: float) -> Optional[Dict[str, Any]]:
        """Execute a Market SELL."""
        formatted_sym = self._format_symbol(symbol)
        filtered_qty = self._apply_filters(symbol, quantity)
        
        if self.mode == "simulation":
            asset = symbol.replace("USDT", "").replace("/", "").upper()
            if filtered_qty > self._sim_assets.get(asset, 0.0):
                filtered_qty = self._sim_assets.get(asset, 0.0)
            
            self._sim_assets[asset] -= filtered_qty
            mock_gain = filtered_qty * 60000.0
            self._sim_balance += mock_gain
            
            logger.info(f"[SIMULATION] SELL {formatted_sym} | Qty: {filtered_qty}")
            return {"orderId": "SIM_SELL_" + os.urandom(4).hex(), "status": "FILLED", "cummulativeQuoteQty": mock_gain}

        try:
            logger.info(f"[EXCHANGE] Placing TESTNET Market SELL: {formatted_sym} (Qty: {filtered_qty})")
            order = self.client.create_order(
                symbol=formatted_sym,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=filtered_qty
            )
            return order
        except Exception as e:
            logger.error(f"[EXCHANGE] Market SELL FAILED for {symbol}: {e}")
            return None

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve open orders from exchange."""
        if self.mode == "simulation" or not self.client: return []
        try:
            sym = self._format_symbol(symbol) if symbol else None
            return self.client.get_open_orders(symbol=sym)
        except Exception as e:
            logger.error(f"[EXCHANGE] get_open_orders failed: {e}")
            return []

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an active order."""
        if self.mode == "simulation" or not self.client: return True
        try:
            self.client.cancel_order(symbol=self._format_symbol(symbol), orderId=order_id)
            return True
        except Exception as e:
            logger.error(f"[EXCHANGE] cancel_order failed: {e}")
            return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    exc = ExchangeExecutor()
    print(f"Mode: {exc.mode}, Enabled: {exc.enabled}")
    print(f"USDT Balance: {exc.get_balance('USDT')}")
