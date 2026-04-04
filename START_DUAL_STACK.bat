@echo off
title TENGU OS: DUAL-STACK ORCHESTRATOR (V11)
echo =============================================================
echo   TENGU OS: UNIVERSAL COMMAND CENTER (CRYPTO + TRADFI)
echo =============================================================
echo.

echo [1/2] Inizializzazione AI-Binance Swarm (Crypto Sector)...
start /min cmd /c "cd /d H:\ai-binance && .\START_STACK.bat"
:: Pausa compatibile di 5 secondi
ping -n 6 127.0.0.1 > nul

echo [2/2] Inizializzazione AI-TradFi Gold Sandbox (Omega Sector)...
start /min cmd /c "cd /d h:\ai-tradfi-parallel && python main.py"

echo.
echo =============================================================
echo   COCKPIT V11 ONLINE: http://127.0.0.1:8088/commander
echo =============================================================
echo.
echo Premi un tasto per chiudere questo orchestratore (i bot rimarranno attivi).
pause > nul

