@echo off
title AVVIA BOT AI (LEGACY BRIDGE)
color 0B
set ROOT_DIR=%~dp0
cd /d "%ROOT_DIR%"

echo =============================================================
echo    REINDIRIZZAMENTO ALLO STACK COMPLETO (2026 READY)
echo    Tengu OS: Crypto + Equity + DeFi + News + Arbitrage
echo =============================================================
echo.

REM Inoltro al nuovo launcher centralizzato
call "%ROOT_DIR%START_STACK.bat"

if %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] Il launcher principale ha fallito.
    pause
)