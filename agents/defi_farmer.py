import time
import logging
import sys
from pathlib import Path
import schedule
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.mock_defi_protocol import MockDeFiProtocol
from services.exchange_executor import ExchangeExecutor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [DEFI_FARMER] %(message)s")
logger = logging.getLogger("defi_farmer")

def job_defi_compound():
    try:
        protocol = MockDeFiProtocol()
        yield_accrued = protocol.compound_yield()
        staked = protocol.get_total_staked()
        
        if staked > 0:
            logger.info(f"Staked in DeFi: ${staked:.2f} | Yield guadagnato nell'ultimo ciclo: +${yield_accrued:.4f} @12% APY")
        else:
            # Se siamo a zero, simuliamo un deposito fittizio da parte dell'engine
            # di 1000$ finti per avviare il testnet del vault.
            logger.info("DeFi Vault vuoto. Deposito fittizio di test di $1000 per verifica Smart Contract.")
            protocol.deposit(1000.0)
            
    except Exception as e:
        logger.error(f"Errore DeFi: {e}")

if __name__ == "__main__":
    logger.info("Avvio DeFi Yield Farmer Agent...")
    schedule.every(10).seconds.do(job_defi_compound)
    
    job_defi_compound()
    
    while True:
        schedule.run_pending()
        time.sleep(1)
