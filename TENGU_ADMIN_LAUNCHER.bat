@echo off
SETLOCAL EnableDelayedExpansion
TITLE TENGU V10 - THE REBIRTH (CONTROL CENTER)

:: --- FORZA IL PATH (Assoluto per stabilità totale) ---
SET "WIN_DIR=C:\Windows\System32"
SET "PS_DIR=C:\Windows\System32\WindowsPowerShell\v1.0"
SET "PATH=%WIN_DIR%;%PS_DIR%;%SystemRoot%;H:\ai-binance\node_modules\.bin"

:: 1. Forza la directory di lavoro
CD /D "H:\ai-binance"

echo ============================================================
echo   TENGU OS V10 - THE AUTONOMOUS SWARM (REBIRTH)
echo   Master Launcher - Robust Control Center Edition
echo ============================================================

echo [TENGU] Resetting environment (Killing Python/Node/Ollama)...
:: Utilizziamo PowerShell con percorso assoluto per reset sicuro (evita stalli di taskkill)
"%PS_DIR%\powershell.exe" -Command "Get-Process | Where-Object { $_.Name -match 'python|node|ollama' } | Stop-Process -Force -ErrorAction SilentlyContinue"
"%WIN_DIR%\timeout.exe" /t 3 /nobreak > nul

:: Assicuriamoci che la cartella logs esista
if not exist logs mkdir logs

echo [TENGU] Starting Infrastructure...

echo [1/5] Launching Ollama API (Gemma 4)...
:: Reindirizziamo solo se il processo non scrive già log propri (Ollama non lo fa in file specifico di default)
start /B ollama serve > logs\ollama_init.log 2>&1

echo [2/5] Launching Memory Bridge (Supermemory)...
start /B npx -y mcp-remote https://api.supermemory.ai/mcp > logs\memory_bridge_bridge.log 2>&1

echo [3/5] Launching WhatsApp MCP Gateway...
start /B node services\whatsapp_mcp\server.js > logs\whatsapp_gateway.log 2>&1

echo [4/5] Launching Dashboard (Port 8088)...
start /B .venv\Scripts\python.exe dashboard\app.py > logs\dashboard_launcher.log 2>&1

echo [TENGU] Waiting for infrastructure to stabilize (10s)...
"%WIN_DIR%\timeout.exe" /t 10 /nobreak > nul

echo [5/5] Launching AI Agent Swarm (Nemotron-3-Super 120B Active)...
:: IMPORTANTE: Non reindirizziamo lo stdout degli agenti qui, perché Python stesso apre i file .log via logging.FileHandler.
:: Reindirizzare il cmd stdout sullo stesso file causerebbe un 'Permission Denied'.
start /B .venv\Scripts\python.exe agents\squad_crypto.py
start /B .venv\Scripts\python.exe services\exchange_executor.py
start /B .venv\Scripts\python.exe agents\risk_controller.py

echo ============================================================
echo   TENGU V10 IS NOW OPERATIONAL
echo   URL:  http://localhost:8088/commander
echo   LOGS: http://localhost:8088/logs
echo ============================================================
echo Premi un tasto per terminare questa finestra (i bot resteranno attivi).
pause
