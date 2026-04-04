@echo off
title TENGU OS - AI TRADING STACK (FULL)
color 0B
set ROOT_DIR=%~dp0
cd /d "%ROOT_DIR%"

echo =============================================================
echo    TENGU OS: STACK DI TRADING AI (VERSIONE APRILE 2026)
echo    [13 AGENTI] Crypto, Equity, DeFi, News, Arbitrage
echo =============================================================
echo.

REM Robust PowerShell Resolver (pwsh -> powershell)
set "PS_CMD=pwsh"
echo | %PS_CMD% -Version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] pwsh non trovato. Cerco powershell standard...
    set "PS_CMD=powershell"
    echo | %PS_CMD% -Version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [ERRORE] PowerShell non trovato nel sistema.
        pause
        exit /b 1
    )
)

echo [AVVIO] Eseguo lo stack dei 13 agenti in corso...
%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File "%ROOT_DIR%START_STACK.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] Lo stack PS1 ha riportato un errore %ERRORLEVEL%.
    pause
) else (
    echo [SUCCESSO] Inizializzazione completata.
    echo Premi un tasto per chiudere questa finestra o lasciala aperta.
    pause
)
