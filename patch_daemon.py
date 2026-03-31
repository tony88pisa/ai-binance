import os
import sys

filepath = r"h:\ai binance\daemon_market_update.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Introduce MAX_OPEN_TRADES
target = "    # Inizializza Wallet Progressivo (Testnet Locale)\n    DEFAULT_BUDGET = 50.0"
replacement = "    # Inizializza Wallet Progressivo (Testnet Locale)\n    DEFAULT_BUDGET = 50.0\n    MAX_OPEN_TRADES = 3"
content = content.replace(target, replacement)

# Add guards before buying
target_buy = """                    if decision["decision"] == "buy":
                        # Calcolo size in EUR basata su wallet progressivo"""

replacement_buy = """                    if decision["decision"] == "buy":
                        # --- RISK CONTROLS ---
                        open_trades = repo.get_open_decisions()
                        if len(open_trades) >= MAX_OPEN_TRADES:
                            # Prevenzione per eccesso posizioni
                            continue
                            
                        # Prevenzione duplicati asset
                        if any(t["asset"] == asset for t in open_trades):
                            continue
                            
                        # Blocco TREND_DOWN o HIGH_VOL_CHAOS
                        if decision["regime"] in ["TREND_DOWN", "HIGH_VOL_CHAOS"]:
                            continue

                        # Calcolo size in EUR basata su wallet progressivo"""

content = content.replace(target_buy, replacement_buy)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
print("Daemon market update patched with risk controls.")
