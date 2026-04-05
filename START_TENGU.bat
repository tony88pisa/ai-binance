@echo off
SETLOCAL EnableDelayedExpansion
TITLE TENGU V10 - ONE CLICK ORCHESTRATOR (LITE)

:: 1. Force Working Dir to script location
CD /D "%~dp0"
SET "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0\;%PATH%"

echo ============================================================
echo   TENGU OS V10 - ONE-CLICK SWARM AUTO-LAUNCHER
echo   "Phased Reset" + "Serial Startup" (April 2026)
echo ============================================================

:: 2. Pre-Check: Kill Everything (Brute Force Mode)
:: Usiamo CMD direttamente così non c'è rischio di freeze in Python
echo [TENGU] Resetting environment (Nuclear Reset Phase 1)...
"%SystemRoot%\System32\taskkill.exe" /F /IM python.exe /T >nul 2>&1
"%SystemRoot%\System32\taskkill.exe" /F /IM node.exe /T >nul 2>&1
"%SystemRoot%\System32\taskkill.exe" /F /IM ollama.exe /T >nul 2>&1

:: 3. Post-Reset Delay
echo [TENGU] Waiting for resource release (5s)...
"%SystemRoot%\System32\timeout.exe" /t 5 /nobreak > nul

:: 4. Start Intelligent Orchestrator V2
echo [TENGU] Handing over to Python Smart Orchestrator...
if exist .venv\Scripts\python.exe (
    .venv\Scripts\python.exe orchestrator_v2.py
) else (
    echo [ERROR] .venv non trovato! Cerco installazione globale di Python...
    python orchestrator_v2.py
)

echo ============================================================
echo   SISTEMA OPERATIVO TENGU CHIUSO
echo ============================================================
pause
