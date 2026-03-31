@echo off
color 4F
echo ========================================================
echo          SBLOCCO DI EMERGENZA MOTORE AI
echo ========================================================
echo.
echo 1. Distruzione dei processi incantati (WinSW)...
taskkill /F /IM "V6-Freqtrade.exe" /T >nul 2>&1
taskkill /F /IM "V6-Daemon.exe" /T >nul 2>&1
taskkill /F /IM "V6-ControlCenter.exe" /T >nul 2>&1
taskkill /F /IM "V6-BotDashboard.exe" /T >nul 2>&1

echo 2. Distruzione dei motori di trading bloccati...
taskkill /F /IM "python.exe" /T >nul 2>&1
taskkill /F /IM "freqtrade.exe" /T >nul 2>&1

echo 3. Avvio pulito dei servizi...
net start V6-ControlCenter
net start V6-BotDashboard
net start V6-Daemon
net start V6-Freqtrade

echo.
echo ========================================================
echo SBLOCCO COMPLETATO CON SUCCESSO!
echo ========================================================
echo 1. Vai alla Dashboard: http://100.84.252.107:8086
echo 2. Premi la combinazione: Ctrl + F5
echo.
pause
