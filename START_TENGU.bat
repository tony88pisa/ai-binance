@echo off
SETLOCAL EnableDelayedExpansion
TITLE TENGU V11 - MICRO-CAPITAL SCALER

:: 1. Forza la directory di lavoro sulla posizione dello script
CD /D "%~dp0"

:: 2. Ripristino del PATH di sistema pulendo il registro corrotto
SET "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0\;C:\Program Files\nodejs;C:\Users\tony1\.npm-global"

echo ============================================================
echo   TENGU OS V11 - MICRO-CAPITAL SCALER AUTO-LAUNCHER
echo   "Grid Trading" + "Sortino/Kelly Math" + 33%% Tax
echo   8 Agenti + Swarm Consensus + SuperBrain (Aprile 2026)
echo ============================================================

:: 3. Controllo Privilegi
echo [TENGU] Controllo privilegi amministratore...
fltmc >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARNING] Non sembri avere privilegi di Amministratore elevati.
    echo Proseguo comunque tra 3 secondi...
    "%SystemRoot%\System32\timeout.exe" /t 3 > nul
) else (
    echo [TENGU] Privilegi ADMIN confermati.
)

:: 4. Pre-Check: Kill Everything (Brute Force Mode via CMD)
echo [TENGU] Resetting environment (Nuclear Reset)...
"%SystemRoot%\System32\taskkill.exe" /F /IM python.exe /T >nul 2>&1
"%SystemRoot%\System32\taskkill.exe" /F /IM node.exe /T >nul 2>&1
"%SystemRoot%\System32\taskkill.exe" /F /IM ollama.exe /T >nul 2>&1

:: 5. Post-Reset Delay
echo [TENGU] Attesa rilascio risorse (5s)...
"%SystemRoot%\System32\timeout.exe" /t 5 /nobreak > nul

:: 6. Lancio AIRI Companion Bridge API
echo [TENGU] Avvio Bridge API...
start "Tengu Bridge API" cmd /k "title Tengu Bridge API && set AI_BINANCE_ROOT=%~dp0&& cd airi-trading-companion\bridge-api && python -m uvicorn main:app --host 0.0.0.0 --port 8090"

:: 7. Lancio AIRI Companion UI (Tamagotchi Mode)
echo [TENGU] Avvio AIRI 3D Companion...
start "Tengu AIRI Companion" cmd /k "title Tengu AIRI Companion && cd airi-trading-companion\airi && pnpm dev:tamagotchi"

:: 8. Lancio Orchestratore V3 (Full Brain)
echo [TENGU] Lancio Orchestratore V3 (Full Brain)...
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe orchestrator_v2.py
) else (
    echo [ERROR] .venv non trovato! Cerco Python globale...
    python orchestrator_v2.py
)

echo ============================================================
echo   SISTEMA OPERATIVO TENGU CHIUSO
echo ============================================================
pause
