import sys
import os
import json
from pathlib import Path
import socket

# Add project root to path
sys.path.append('h:/ai-binance')

from config.settings import get_settings
from services.exchange_executor import ExchangeExecutor

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def verify():
    settings = get_settings()
    executor = ExchangeExecutor()
    
    print("--- ANTIGRAVITY REFACTOR CERTIFICATION ---")
    print(f"PID: {os.getpid()}")
    print(f"Project Root: {settings.paths.project_root}")
    
    print("\n[SETTINGS RUNTIME DUMP]")
    runtime = {
        "exchange": {
            "name": settings.exchange.name,
            "mode": settings.exchange.mode,
            "testnet_enabled": executor.mode == "testnet",
            "fallback_active": executor.mode != settings.exchange.mode
        },
        "trading": {
            "wallet_size": settings.trading.wallet_size,
            "stake_currency": settings.trading.stake_currency,
            "pairs": settings.trading.pairs,
            "dry_run": settings.trading.dry_run
        },
        "dashboard": {
            "host": settings.dashboard.host,
            "port": settings.dashboard.port,
            "effective_url": f"http://{settings.dashboard.host}:{settings.dashboard.port}"
        },
        "risk": {
            "emergency_threshold": settings.trading.wallet_size * 0.90
        }
    }
    print(json.dumps(runtime, indent=4))

    print("\n[.env SOURCE TRACE]")
    env_vars = [
        "EXCHANGE_NAME", "EXCHANGE_MODE", "INITIAL_CAPITAL", 
        "CAPITAL_CURRENCY", "DASHBOARD_PORT", "BINANCE_TESTNET_API_KEY"
    ]
    for var in env_vars:
        val = os.getenv(var, "NOT SET")
        masked = val[:4] + "..." if len(val) > 8 and "KEY" in var else val
        print(f"{var}: {masked}")

    print("\n[PORT AVAILABILITY CHECK]")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((settings.dashboard.host, settings.dashboard.port))
    if result == 0:
        print(f"PORT {settings.dashboard.port}: ACTIVE (LISTENING)")
    else:
        print(f"PORT {settings.dashboard.port}: INACTIVE (NOT LISTENING)")
    sock.close()

if __name__ == "__main__":
    verify()
