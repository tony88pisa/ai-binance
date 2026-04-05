"""
TENGU V10 — ORCHESTRATOR V3 (FULL BRAIN)
Avvia l'intero ecosistema Tengu in ordine cronologico.
Tutti i moduli di intelligenza sono attivati.
"""
import subprocess
import time
import os
import sys
import socket
import datetime
from pathlib import Path

# --- CONFIGURAZIONE ---
PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
LOGS_DIR = PROJECT_ROOT / "logs"

# Percorsi comuni per trovare ollama
EXTRA_PATHS = [
    r"C:\Windows\System32",
    r"C:\Users\tony1\AppData\Local\Programs\Ollama",
    r"C:\Program Files\Ollama",
]

def find_cmd(name):
    """Cerca un eseguibile nei percorsi extra o nel PATH."""
    import shutil
    res = shutil.which(name)
    if res: return f'"{res}"'
    
    exts = [".exe", ".cmd", ".bat"] if os.name == 'nt' else [""]
    for path in EXTRA_PATHS:
        for ext in exts:
            p = Path(path) / (name + ext)
            if p.exists():
                return f'"{p}"'
    return name

def is_port_open(port, host='127.0.0.1'):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((host, port)) == 0
    except:
        return False

def start_service(name, cmd, wait_port=None, timeout=40):
    ts = datetime.datetime.now().strftime("%H%M%S")
    log_file = LOGS_DIR / f"{name}_init_{ts}.log"
    print(f"[TENGU] Avvio {name}...")
    try:
        p = subprocess.Popen(
            cmd, 
            stdout=open(log_file, "w"), 
            stderr=subprocess.STDOUT, 
            shell=True, 
            creationflags=subprocess.CREATE_NEW_CONSOLE if "agents" in name.lower() else 0
        )
    except Exception as e:
        print(f"[ERROR] Impossibile avviare {name}: {e}")
        return None
    
    if wait_port:
        print(f"      In attesa sulla porta {wait_port} (timeout {timeout}s)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if is_port_open(wait_port):
                print(f"      [READY] {name} attivo.")
                return p
            time.sleep(1)
        print(f"      [WARN] {name} non ha risposto in tempo. Procedo.")
    else:
        time.sleep(2)
    return p

def main():
    print("============================================================")
    print("   TENGU V11 — MICRO-CAPITAL SCALER ORCHESTRATOR")
    print("   Tutti i moduli abilitati: Grid, Momentum, Tax-Aware 33%.")
    print("============================================================")
    
    os.chdir(PROJECT_ROOT)
    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir()

    # ═══════════════════════════════════════════
    # FASE 1: INFRASTRUTTURA CORE
    # ═══════════════════════════════════════════
    print("\n[FASE 1] Infrastruttura Core...")
    
    # 1.1 Ollama (LLM locale)
    ollama_bin = find_cmd("ollama")
    start_service("Ollama", f"{ollama_bin} serve", wait_port=11434)
    
    # 1.2 Pre-caricamento Gemma 4
    print("[TENGU] Pre-caricamento Gemma 4 (gemma4:e4b)...")
    try:
        subprocess.run(f"{ollama_bin} run gemma4:e4b \"ok\"", shell=True, timeout=60, capture_output=True)
        print("      [READY] Gemma 4 caricato su GPU.")
    except:
        print("      [WARN] Caricamento lento. Gli agenti riproveranno.")


    # ═══════════════════════════════════════════
    # FASE 2: DASHBOARD & MONITORAGGIO
    # ═══════════════════════════════════════════
    print("\n[FASE 2] Dashboard & Monitoraggio...")
    start_service("Dashboard", f'"{PYTHON_EXE}" -m dashboard.app', wait_port=8088)

    # ═══════════════════════════════════════════
    # FASE 3: CERVELLO OPERATIVO (AGENTI CORE)
    # ═══════════════════════════════════════════
    print("\n[FASE 3] Cervello Operativo (Agenti Core)...")
    
    # 3.1 Squad Crypto — Analista di mercato principale
    start_service("Agents_Squad", f'"{PYTHON_EXE}" -m agents.squad_crypto')
    time.sleep(2)
    
    # 3.2 Squad Equity — Analisi azioni e materie prime  
    start_service("Agents_Equity", f'"{PYTHON_EXE}" -m agents.squad_equity')
    time.sleep(2)
    
    # 3.3 Risk Controller — Supervisor Nemotron 120B
    start_service("Agents_Risk", f'"{PYTHON_EXE}" -m agents.risk_controller')
    time.sleep(2)

    # ═══════════════════════════════════════════
    # FASE 4: INTELLIGENZA AVANZATA
    # ═══════════════════════════════════════════
    print("\n[FASE 4] Intelligenza Avanzata...")
    
    # 4.1 Dream Agent — Consolidamento memoria ogni 30 min
    #     + Skill Generator: auto-genera nuove strategie da NVIDIA Teacher
    #     + 4-Phase Prompt: Orient → Gather → Consolidate → Prune
    start_service("Agents_Dream", f'"{PYTHON_EXE}" -m agents.dream_agent')
    time.sleep(2)
    
    # 4.2 Coordinator — Supervisore globale con circuit breaker
    start_service("Agents_Coordinator", f'"{PYTHON_EXE}" -m agents.coordinator')
    time.sleep(2)
    
    # 4.3 News Trader V2 — Sentiment reale da RSS + Fear & Greed
    start_service("Agents_News", f'"{PYTHON_EXE}" -m agents.news_trader')
    time.sleep(2)

    # 4.4 Auto Optimizer — Brute Force offline
    start_service("Auto_Optimizer", f'"{PYTHON_EXE}" -m ai.auto_optimizer')

    # ═══════════════════════════════════════════
    # COMPLETATO
    # ═══════════════════════════════════════════
    print("\n============================================================")
    print("   🧠 TENGU V11 — MICRO-CAP SCALER OPERATIVO")
    print("   ─────────────────────────────────────")
    print("   Dashboard:  http://localhost:8088")
    print("   ─────────────────────────────────────")
    print("   Agenti Operativi:")
    print("     ● Squad Crypto      (Gem Hunter + Grid/Momentum)")
    print("     ● Squad Equity      (Multi-Asset Diversification)")
    print("     ● Risk Controller   (Kelly Size + 33% Tax Reserve)")
    print("     ● Coordinator       (Circuit Breaker + Notifiche)")
    print("   Intelligenza:")
    print("     ● Dream Agent       (Memory Consolidation)")
    print("     ● News Trader V2    (DDG Scraping + Event Hunting)")
    print("     ● Auto Optimizer    (Sortino + Grid Validation)")
    print("   Layer Decisionale:")
    print("     ● MCP Tools         (Trendings + Semantic Web)")
    print("     ● Swarm Consensus   (Rigorous Peer Review)")
    print("   ─────────────────────────────────────")
    print("   Premi CTRL+C per chiudere tutto.")
    print("============================================================")
    
    try:
        while True: time.sleep(10)
    except KeyboardInterrupt:
        print("\n[TENGU] Chiusura orchestratore.")

if __name__ == "__main__":
    main()

