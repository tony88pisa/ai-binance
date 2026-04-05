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

# Percorsi comuni per trovare ollama/node/npx
EXTRA_PATHS = [
    r"C:\Windows\System32",
    r"C:\Program Files\nodejs",
    r"C:\Users\tony1\AppData\Local\Programs\Ollama",
    r"C:\Program Files\Ollama",
    os.path.expandvars(r"%AppData%\npm")
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
    print("   TENGU V10 — ORCHESTRATORE V3 (FULL BRAIN)")
    print("   Tutti i moduli di intelligenza attivati.")
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

    # 1.3 Supermemory Bridge (Memoria Semantica)
    npx_bin = find_cmd("npx")
    start_service("MemoryBridge", f"{npx_bin} -y mcp-remote https://api.supermemory.ai/mcp")
    
    # 1.4 WhatsApp Hub
    node_bin = find_cmd("node")
    start_service("WhatsApp", f"{node_bin} services/whatsapp_mcp/server.js")

    # ═══════════════════════════════════════════
    # FASE 2: DASHBOARD & MONITORAGGIO
    # ═══════════════════════════════════════════
    print("\n[FASE 2] Dashboard & Monitoraggio...")
    start_service("Dashboard", f'"{PYTHON_EXE}" dashboard/app.py', wait_port=8088)

    # ═══════════════════════════════════════════
    # FASE 3: CERVELLO OPERATIVO (AGENTI CORE)
    # ═══════════════════════════════════════════
    print("\n[FASE 3] Cervello Operativo (Agenti Core)...")
    
    # 3.1 Squad Crypto — Analista di mercato principale
    start_service("Agents_Squad", f'"{PYTHON_EXE}" agents/squad_crypto.py')
    time.sleep(2)
    
    # 3.2 Risk Controller — Supervisor Nemotron 120B
    start_service("Agents_Risk", f'"{PYTHON_EXE}" agents/risk_controller.py')
    time.sleep(2)

    # ═══════════════════════════════════════════
    # FASE 4: INTELLIGENZA AVANZATA (MODULI DORMIENTI ATTIVATI)
    # ═══════════════════════════════════════════
    print("\n[FASE 4] Intelligenza Avanzata (Moduli Attivati)...")
    
    # 4.1 Dream Agent — Consolidamento memoria ogni 2h
    #     Analizza errori passati e genera strategie tattiche rolling
    start_service("Agents_Dream", f'"{PYTHON_EXE}" agents/dream_agent.py')
    time.sleep(2)
    
    # 4.2 Coordinator — Supervisore globale con circuit breaker
    #     Impedisce budget overflow e genera report di salute
    start_service("Agents_Coordinator", f'"{PYTHON_EXE}" agents/coordinator.py')

    # ═══════════════════════════════════════════
    # COMPLETATO
    # ═══════════════════════════════════════════
    print("\n============================================================")
    print("   🧠 TENGU V10 — FULL BRAIN OPERATIVO")
    print("   ─────────────────────────────────────")
    print("   Dashboard:  http://localhost:8088")
    print("   Logs:       http://localhost:8088/logs")
    print("   ─────────────────────────────────────")
    print("   Agenti Attivi:")
    print("     ● Squad Crypto    (Analisi di Mercato)")
    print("     ● Risk Controller (Supervisore Nemotron 120B)")
    print("     ● Dream Agent     (Consolidamento Memoria 2h)")
    print("     ● Coordinator     (Circuit Breaker + Reports)")
    print("   ─────────────────────────────────────")
    print("   Premi CTRL+C per chiudere tutto.")
    print("============================================================")
    
    try:
        while True: time.sleep(10)
    except KeyboardInterrupt:
        print("\n[TENGU] Chiusura orchestratore.")

if __name__ == "__main__":
    main()
