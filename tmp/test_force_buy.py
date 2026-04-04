import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.append('h:/ai-binance')

from services.exchange_executor import ExchangeExecutor

def test_force_buy():
    executor = ExchangeExecutor()
    asset = "BNB/USDT"
    amount_usdt = 25.0
    
    print(f"--- FORCING BUY TEST ON {asset} ---")
    print(f"Mode: {executor.mode.upper()}")
    
    order = executor.place_market_buy(asset, amount_usdt)
    if order:
        print(f"SUCCESS! Order ID: {order['orderId']}")
        # print(json.dumps(order, indent=2))
    else:
        print("FAILED to place order.")

if __name__ == "__main__":
    test_force_buy()
