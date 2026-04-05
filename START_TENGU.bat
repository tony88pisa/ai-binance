@echo off
SETLOCAL EnableDelayedExpansion
TITLE TENGU V10 - FULL BRAIN ORCHESTRATOR

:: 1. Forza la directory di lavoro sulla posizione dello script
CD /D "%~dp0"

:: 2. Forza il PATH di sistema
SET "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0\;%PATH%"

echo ============================================================
echo   TENGU OS V10 - FULL BRAIN AUTO-LAUNCHER
echo   "Nuclear Reset" + "4-Phase Smart Init" (Aprile 2026)
echo   Agenti Attivati: Squad, Risk, Dream, Coordinator
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

:: 6. Lancio Orchestratore V3 (Full Brain)
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
