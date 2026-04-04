@echo off
SETLOCAL EnableDelayedExpansion
TITLE TENGU V10 - FINAL RESET (APRIL 2026)

:: --- CONFIGURAZIONE PERCORSI ASSOLUTI (CRUCIALE) ---
SET "WIN_DIR=C:\Windows\System32"
SET "PS_DIR=C:\Windows\System32\WindowsPowerShell\v1.0"
SET "NODE_DIR=C:\Program Files\nodejs"
SET "NPX_CMD=%NODE_DIR%\npx.cmd"
SET "PATH=%WIN_DIR%;%PS_DIR%;%NODE_DIR%;%SystemRoot%;H:\ai-binance\node_modules\.bin"

:: 1. Forza la directory di lavoro assoluta su HDD H:
H:
CD \ai-binance

echo ============================================================
echo   TENGU OS V10 - FULL SYSTEM RESET (ULTIMATE FIX)
echo   Risoluzione conflitti di lock e percorsi "npx"
echo ============================================================

echo [1/4] Controllo Amministratore...
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [CRITICAL ERROR] DEVI ESEGUIRE COME AMMINISTRATORE!
    pause
    exit /b 1
)

echo [2/4] Reset Nucleare (Uccisione forzata di ogni processo residuo)...
:: Usiamo taskkill e PowerShell in cascata per non lasciare scampo ai processi zombi
"%WIN_DIR%\taskkill.exe" /F /IM python.exe /T >nul 2>&1
"%WIN_DIR%\taskkill.exe" /F /IM node.exe /T >nul 2>&1
"%WIN_DIR%\taskkill.exe" /F /IM ollama.exe /T >nul 2>&1
"%PS_DIR%\powershell.exe" -Command "Get-Process | Where-Object { $_.Name -match 'python|node|ollama' } | Stop-Process -Force -ErrorAction SilentlyContinue"

:: Attesa per il rilascio dei file log bloccati
echo [WAIT] Attesa rilascio file handles...
"%WIN_DIR%\timeout.exe" /t 5 /nobreak > nul

echo [3/4] Pulizia Log Generica...
:: Proviamo a cancellare i log; se fallisce, usiamo un nome file alternativo
del /F /Q logs\* >nul 2>&1
if not exist logs mkdir logs

echo [4/4] Inizio Sequenza di Avvio (Fase 1: Infra)...
echo ------------------------------------------------------------

echo [START] Ollama (Gemma 4)...
:: Cambiamo nome al file log di init per bypassare eventuali lock residui
start /B ollama serve > logs\ollama_boot_%RANDOM%.log 2>&1

echo [START] Supermemory Bridge...
if exist "%NPX_CMD%" (
    start /B "" "%NPX_CMD%" -y mcp-remote https://api.supermemory.ai/mcp > logs\memory_bridge.log 2>&1
) else (
    echo [WARNING] npx non trovato in %NODE_DIR%. Provo nel PATH generico...
    start /B npx -y mcp-remote https://api.supermemory.ai/mcp > logs\memory_bridge.log 2>&1
)

echo [START] WhatsApp Hub...
start /B node services\whatsapp_mcp\server.js > logs\whatsapp.log 2>&1

echo [START] Dashboard (Port 8088)...
start /B .venv\Scripts\python.exe dashboard\app.py > logs\dashboard_%RANDOM%.log 2>&1

echo [STATUS] Stabilizzazione in corso (10s)...
"%WIN_DIR%\timeout.exe" /t 10 /nobreak > nul

echo [START] AI Swarm (Gemma 4 + Nemotron 120B)...
:: Lancio degli agenti core (No redirect per evitare PermissionError)
start "SQUAD_CRYPTO" /MIN .venv\Scripts\python.exe agents\squad_crypto.py
start "EXECUTOR" /MIN .venv\Scripts\python.exe services\exchange_executor.py
start "RISK" /MIN .venv\Scripts\python.exe agents\risk_controller.py

echo ============================================================
echo   TENGU V10 IS NOW OPERATIONAL
echo   URL: http://localhost:8088/commander
echo   LOGS: http://localhost:8088/logs
echo ============================================================
echo [AVVISO] Se non trovi npx, installa Node.js per tutti gli utenti.
pause
