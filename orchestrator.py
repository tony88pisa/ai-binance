import subprocess
import time
import os
import sys
import socket
import traceback
from pathlib import Path

# --- CONFIGURAZIONE ---
PROJECT_ROOT = Path(__file__).resolve().parent
# Utilizziamo l'eseguibile di python che sta eseguendo questo script
PYTHON_EXE = sys.executable
LOGS_DIR = PROJECT_ROOT / "logs"

# Comandi di sistema assoluti (Blindati per Windows 11)
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
TASKKILL = r"C:\Windows\System32\taskkill.exe"

def is_port_open(port, host='127.0.0.1'):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((host, port)) == 0
    except:
        return False

def nuke_processes():
    my_pid = os.getpid()
    print(f"[TENGU] Resetting environment (Selective Nuclear Kill, PID: {my_pid})...")
    sys.stdout.flush()
    
    if os.name == 'nt':
        try:
            # Metodo Ultra-Safe: cerchiamo i processi Python che hanno nel comando "agents", "dashboard" o "services"
            # Ma MAI quello che contiene "orchestrator.py"
            ps_cmd = (
                'Get-CimInstance Win32_Process | '
                'Where-Object { ($_.Name -eq "python.exe" -or $_.Name -eq "node.exe" -or $_.Name -eq "ollama.exe") '
                f'-and $_.ProcessId -ne {my_pid} '
                '-and $_.CommandLine -notmatch "orchestrator.py" } | '
                'Invoke-CimMethod -MethodName Terminate'
            )
            subprocess.run([POWERSHELL, "-NoProfile", "-Command", ps_cmd], capture_output=True)
            
            # Kill residui per node e ollama se necessario
            subprocess.run([TASKKILL, "/F", "/IM", "node.exe", "/T"], capture_output=True)
            subprocess.run([TASKKILL, "/F", "/IM", "ollama.exe", "/T"], capture_output=True)
        except Exception as e:
            print(f"[WARN] Errore durante il nuke: {e}")
            sys.stdout.flush()
    time.sleep(2)

def cleanup_logs():
    print("[TENGU] Cleaning log locks...")
    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir()
    for f in LOGS_DIR.glob("*"):
        try:
            # Rimuoviamo solo se non è un file di sistema
            if f.is_file():
                os.remove(f)
        except:
            pass

def start_service(name, cmd, wait_port=None, timeout=30):
    print(f"[TENGU] Launching {name}...")
    log_file = LOGS_DIR / f"{name}_init.log"
    try:
        # Usiamo shell=True per gestire i comandi complessi
        p = subprocess.Popen(cmd, stdout=open(log_file, "w"), stderr=subprocess.STDOUT, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE if "agents" in name.lower() else 0)
    except Exception as e:
        print(f"[ERROR] Fallito avvio di {name}: {e}")
        return None
    
    if wait_port:
        print(f"      Waiting for port {wait_port}...")
        start = time.time()
        while time.time() - start < timeout:
            if is_port_open(wait_port):
                print(f"      [READY] {name} is alive.")
                return p
            time.sleep(1)
        print(f"      [WARN] {name} starting slowly.")
    else:
        time.sleep(2)
    return p

def main():
    try:
        os.chdir(PROJECT_ROOT)
        nuke_processes()
        cleanup_logs()
        
        print("\n[TENGU] --- INIZIO SEQUENZA DI AVVIO ---")
        
        # 1. Ollama
        start_service("Ollama", "ollama serve", wait_port=11434)
        
        # 2. Supermemory
        start_service("MemoryBridge", 'npx -y mcp-remote https://api.supermemory.ai/mcp')
        
        # 3. WhatsApp
        start_service("WhatsApp", 'node services/whatsapp_mcp/server.js')
        
        # 4. Dashboard
        start_service("Dashboard", f'"{PYTHON_EXE}" dashboard/app.py', wait_port=8088)
        
        print("\n[TENGU] --- AVVIO AGENTI AI ---")
        start_service("Agents_Squad", f'"{PYTHON_EXE}" agents/squad_crypto.py')
        time.sleep(2)
        start_service("Agents_Risk", f'"{PYTHON_EXE}" agents/risk_controller.py')
        
        print("\n============================================================")
        print("   TENGU V10: SISTEMA OPERATIVO")
        print("   Dashboard: http://localhost:8088")
        print("============================================================")
        print("Mantenere questa finestra aperta per il monitoraggio.")
        while True: time.sleep(10)
    except Exception:
        print("\n[CRITICAL ERROR] L'Orchestratore è crashato:")
        traceback.print_exc()
        input("\nPremi INVIO per chiudere...")

if __name__ == "__main__":
    main()
