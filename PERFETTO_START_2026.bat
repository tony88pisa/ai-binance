@echo off
SETLOCAL EnableDelayedExpansion
TITLE TENGU V10 - THE REBIRTH (CONTROL CENTER)

:: --- FORZA IL PATH (Risolve problemi di ambiente dell'utente) ---
SET "WIND_DIR=C:\Windows\System32"
SET "PS_DIR=C:\Windows\System32\WindowsPowerShell\v1.0"
SET "PATH=%PATH%;%WIND_DIR%;%PS_DIR%;H:\ai-binance\node_modules\.bin"

echo ============================================================
echo   TENGU OS V10 - THE AUTONOMOUS SWARM (APRIL 2026)
echo   Master Launcher - Robust Control Center Edition
echo ============================================================

echo [TENGU] Resetting environment (Killing Python/Node/Ollama)...
:: Utilizziamo PowerShell con percorso assoluto per reset sicuro
"%PS_DIR%\powershell.exe" -Command "Get-Process | Where-Object { $_.Name -match 'python|node|ollama' } | Stop-Process -Force -ErrorAction SilentlyContinue"
"%WIND_DIR%\timeout.exe" /t 3 /nobreak > nul

:: Assicuriamoci che la cartella logs esista
if not exist logs mkdir logs

echo [TENGU] Starting Infrastructure...

echo [1/5] Launching Ollama API (Gemma 4)...
start /B ollama serve > logs\ollama_init.log 2>&1

echo [2/5] Launching Memory Bridge (Supermemory)...
:: Verifichiamo npx (solitamente parte di node)
start /B npx -y mcp-remote https://api.supermemory.ai/mcp > logs\memory_bridge.log 2>&1

echo [3/5] Launching WhatsApp MCP Gateway...
start /B node services\whatsapp_mcp\server.js > logs\whatsapp.log 2>&1

echo [4/5] Launching Dashboard (Port 8088)...
:: Python venv locale
start /B .venv\Scripts\python.exe dashboard\app.py > logs\dashboard.log 2>&1

echo [TENGU] Waiting for infrastructure to stabilize (10s)...
"%WIND_DIR%\timeout.exe" /t 10 /nobreak > nul

echo [5/5] Launching AI Agent Swarm (Nemotron-3-Super 120B Active)...
:: Lancio degli agenti core in background
start /B .venv\Scripts\python.exe agents\squad_crypto.py > logs\squad_crypto.log 2>&1
start /B .venv\Scripts\python.exe services\exchange_executor.py > logs\executor.log 2>&1
start /B .venv\Scripts\python.exe agents\risk_controller.py > logs\supervisor.log 2>&1

echo ============================================================
echo   TENGU V10 IS NOW OPERATIONAL
echo   URL:  http://localhost:8088/commander
echo   LOGS: http://localhost:8088/logs
echo ============================================================
echo Premi un tasto per chiudere questa finestra (i bot resteranno attivi).
pause
