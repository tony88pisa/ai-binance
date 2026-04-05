import subprocess
import time
import os
import sys
import socket
from pathlib import Path

# --- CONFIGURAZIONE ---
PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
LOGS_DIR = PROJECT_ROOT / "logs"

# Percorsi comuni per trovare ollama/node/npx
EXTRA_PATHS = [
    r"C:\Windows\System32",
    r"C:\Program Files\nodejs",
    r"C:\Users\tony1\AppData\Local\Programs\Ollama", # Percorso utente Ollama
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
    print(f"[TENGU] Avvio {name}...")
    import datetime
    ts = datetime.datetime.now().strftime("%H%M%S")
    log_file = LOGS_DIR / f"{name}_init_{ts}.log"
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
        print(f"      [WARN] {name} non ha risposto in tempo. Procedo comunque.")
    else:
        time.sleep(2)
    return p

def main():
    print("============================================================")
    print("   TENGU V10 - ORCHESTRATORE SMART (V2.1 - PATH FIX)")
    print("============================================================")
    
    os.chdir(PROJECT_ROOT)
    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir()

    # 1. Infrastruttura (In ordine cronologico)
    ollama_bin = find_cmd("ollama")
    start_service("Ollama", f"{ollama_bin} serve", wait_port=11434)
    
    print("[TENGU] Pre-caricamento modello Gemma 4 (gemma4:e4b)...")
    # Usiamo un timeout per evitare che blocchi tutto se non riesce a tirare il modello
    try:
        subprocess.run(f"{ollama_bin} run gemma4:e4b \"Ciao\"", shell=True, timeout=60, capture_output=True)
        print("      [READY] Gemma 4 caricato.")
    except:
        print("      [WARN] Caricamento modello lento o fallito. Gli agenti riproveranno internamente.")

    npx_bin = find_cmd("npx")
    start_service("MemoryBridge", f"{npx_bin} -y mcp-remote https://api.supermemory.ai/mcp")
    
    node_bin = find_cmd("node")
    start_service("WhatsApp", f"{node_bin} services/whatsapp_mcp/server.js")
    
    # 2. Dashboard
    start_service("Dashboard", f'"{PYTHON_EXE}" dashboard/app.py', wait_port=8088)
    
    # 3. Agenti AI (Nemotron 120B Supervisore)
    print("\n[TENGU] Lancio dello Swarm di Agenti...")
    start_service("Agents_Squad", f'"{PYTHON_EXE}" agents/squad_crypto.py')
    time.sleep(2)
    start_service("Agents_Risk", f'"{PYTHON_EXE}" agents/risk_controller.py')
    
    print("\n============================================================")
    print("   SISTEMA OPERATIVO TENGU ATTIVO (V10)")
    print("   Dashboard: http://localhost:8088")
    print("   Fai riferimento ai tab 'Logs' per monitorare gli agenti.")
    print("============================================================")
    
    try:
        while True: time.sleep(10)
    except KeyboardInterrupt:
        print("\n[TENGU] Chiusura orchestratore.")

if __name__ == "__main__":
    main()
