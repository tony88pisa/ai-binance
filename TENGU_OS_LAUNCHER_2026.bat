@echo off
:: Forza il passaggio alla cartella dove risiede il file .bat (fondamentale per Esegui come Amministratore)
cd /d "%~dp0"

TITLE TENGU OS V10 - MASTER LAUNCHER (APRIL 2026)
COLOR 0B

echo ============================================================
echo   TENGU OS V10 - THE AUTONOMOUS SWARM (APRIL 2026)
echo   Master Launcher - PowerShell Orchestration (ADMIN SAFE)
echo ============================================================
echo.

:: Uso il path assoluto per PowerShell e il path relativo corretto ora che siamo nella root
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "scripts\launcher.ps1"

if %errorlevel% neq 0 (
    echo.
    echo [!] Errore durante l'esecuzione del launcher.
    echo.
    pause
)
