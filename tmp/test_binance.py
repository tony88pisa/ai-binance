import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from services.exchange_executor import ExchangeExecutor

def test_connectivity():
    logging.basicConfig(level=logging.INFO)
    print("=== TEST CONNETTIVITÀ BINANCE TESTNET ===")
    
    executor = ExchangeExecutor()
    
    if not executor.enabled:
        print("\n[ERRORE] L'executor è disabilitato.")
        print("Cosa controllare:")
        print("1. Hai inserito le API Key nel file .env?")
        print("2. EXCHANGE_MODE è impostato su 'testnet'?")
        print("3. La tua connessione internet permette di raggiungere testnet.binance.vision?")
        return

    print(f"\n[OK] Modalità: {executor.mode.upper()}")
    
    try:
        usdt_balance = executor.get_balance("USDT")
        print(f"[OK] Saldo USDT: {usdt_balance}")
        
        btc_balance = executor.get_balance("BTC")
        print(f"[OK] Saldo BTC: {btc_balance}")
        
        open_orders = executor.get_open_orders()
        print(f"[OK] Ordini Aperti: {len(open_orders)}")
        
        print("\n=== TEST COMPLETATO CON SUCCESSO ===")
        print("Il bot è pronto per operare su Binance Testnet.")
        
    except Exception as e:
        print(f"\n[ERRORE] Durante il test: {e}")

if __name__ == "__main__":
    test_connectivity()
