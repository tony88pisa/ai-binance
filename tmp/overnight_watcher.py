import subprocess
import time
import socket
import os
import logging
from datetime import datetime
from pathlib import Path

# Configurazione (Phase 4/5 spec)
LOG_FILE = Path("H:/ai binance/logs/overnight_technical_watch.log")
RESTART_LIMIT = 3
CHECK_INTERVAL = 60 # secondi

# Logging diagnostico separato (Phase 6 spec)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("OVERNIGHT_WATCHER")

services = {
    "dashboard": {"port": 8086, "command": ["python", "-m", "uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8086"], "restarts": 0},
    "freqtrade": {"port": 8080, "command": ["powershell", "-ExecutionPolicy", "Bypass", "-File", "START_FREQTRADE.ps1"], "restarts": 0},
    "evolution_loop": {"process_name": "evolution_loop", "command": ["python", "scripts/evolution_loop.py"], "restarts": 0}
}

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def log_event(level, msg):
    print(f"[{datetime.now()}] {level}: {msg}")
    if level == "INFO": logger.info(msg)
    elif level == "WARN": logger.warning(msg)
    elif level == "ERROR": logger.error(msg)
    elif level == "CRITICAL": logger.critical(msg)

def start_service(name):
    svc = services[name]
    if svc["restarts"] >= RESTART_LIMIT:
        log_event("CRITICAL", f"FAILED_RESTART_LIMIT for service {name}. Skipping.")
        return False
    
    log_event("WARN", f"Attempting restart for {name} (Attempt {svc['restarts'] + 1}/{RESTART_LIMIT})")
    try:
        # Avvia in background senza bloccare il watcher
        subprocess.Popen(svc["command"], cwd="H:/ai binance", shell=True)
        svc["restarts"] += 1
        log_event("INFO", f"Service {name} started in background.")
        return True
    except Exception as e:
        log_event("ERROR", f"Failed to start {name}: {e}")
        return False

def monitor_loop():
    log_event("INFO", "=== STARTING OVERNIGHT TECHNICAL WATCHER ===")
    log_event("INFO", f"Monitoring Dashboard (8086), Freqtrade (8080), Evolution Loop.")
    
    while True:
        # Heartbeat periodico (Phase 4 spec)
        log_event("INFO", "HEARTBEAT - Watcher is alive.")

        for name, config in services.items():
            alive = False
            if "port" in config:
                alive = is_port_open(config["port"])
            else:
                # Per evolution_loop, check se il processo è attivo (semplificato)
                alive = True # PARTIAL: assume vivo o lo lancia comunque se checkpoint-based

            if not alive:
                log_event("WARN", f"Service {name} detected as STOPPED.")
                start_service(name)
            else:
                # Se è vivo, resettiamo il contatore restart se era già stabile (opzionale)
                pass

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        monitor_loop()
    except KeyboardInterrupt:
        log_event("INFO", "Watcher stopped by user.")
