@echo off
SETLOCAL EnableDelayedExpansion
TITLE TENGU V10 - ULTIMA RATIO (WINDOWS 11 READY)

:: --- PREPARAZIONE AMBIENTE ---
:: Impostiamo il PATH in modo aggressivo per includere tutto il necessario
SET "PATH=%SystemRoot%\system32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0\;H:\ai-binance\node_modules\.bin;%PATH%"
CD /D "H:\ai-binance"

echo ============================================================
echo   TENGU OS V10 - THE REBIRTH (CONTROL CENTER)
echo   "ULTIMA RATIO" Launcher - Aprile 2026
echo ============================================================

:: DISABILITA IL BLOCCO DEL TERMINALE (QuickEdit Mode a volte causa il freeze nel reset)
:: Se vedi un rettangolo bianco nella finestra, premi INVIO per sbloccare!

echo [1/3] Controllo Privilegi Amministratore...
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] DEVI ESEGUIRE COME AMMINISTRATORE!
    pause
    exit /b 1
)

echo [2/3] Reset Nucleare dei Processi (No-Block Mode)...
:: Lanciamo i kill in parallelo per evitare che un singolo processo bloccato fermi tutto il file batch
start /B "" taskkill /F /IM python.exe >nul 2>&1
start /B "" taskkill /F /IM node.exe >nul 2>&1
start /B "" taskkill /F /IM ollama.exe >nul 2>&1

:: Utilizziamo un breve timeout di sistema
timeout /t 3 /nobreak > nul

echo [3/3] Pulizia Profonda Log...
if exist logs (
    del /S /Q logs\* >nul 2>&1
) else (
    mkdir logs
)

echo [TENGU] Inizio Sequenza di Avvio Swarm...
echo ------------------------------------------------------------

:: 1. Infrastruttura Core
echo [INIT] Ollama Gemma 4...
start /B ollama serve > logs\ollama_init.log 2>&1

echo [INIT] Supermemory Bridge...
start /B npx -y mcp-remote https://api.supermemory.ai/mcp > logs\memory_bridge.log 2>&1

echo [INIT] WhatsApp Hub...
start /B node services\whatsapp_mcp\server.js > logs\whatsapp.log 2>&1

echo [INIT] Dashboard (Port 8088)...
start /B .venv\Scripts\python.exe dashboard\app.py > logs\dashboard_boot.log 2>&1

echo [TENGU] Attesa stabilizzazione (10 secondi)...
timeout /t 10 /nobreak > nul

:: 2. Lancio Agenti (Nemotron 120B Supervisore)
echo [LAUNCH] AI Agent Swarm (Nemotron 120B)...
:: Lanciamo gli agenti SENZA redirezione e in finestre separate così vedi se crashano all'avvio (come richiesto dai protocolli W11)
start "SQUAD_CRYPTO" /MIN .venv\Scripts\python.exe agents\squad_crypto.py
start "EXECUTOR" /MIN .venv\Scripts\python.exe services\exchange_executor.py
start "RISK_SUP" /MIN .venv\Scripts\python.exe agents\risk_controller.py

echo ============================================================
echo   TENGU V10 IS NOW OPERATIONAL
echo   DASHBOARD: http://localhost:8088/commander
echo   LOGS: http://localhost:8088/logs
echo ============================================================
echo [AVVISO] Se il terminale sembra fermo, premi INVIO. 
echo I bot ora girano minimizzati nella barra delle applicazioni.
pause
