# START_DUAL_STACK.ps1 - TENGU OS UNIVERSAL LAUNCHER
# Versione 11.0: Crypto + TradFi Night Monitoring

Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "   TENGU OS: UNIVERSAL COMMAND CENTER (CRYPTO + TRADFI)" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan

# 1. PULIZIA RADICALE
Write-Host "[1/4] Pulizia processi zombie in corso..." -ForegroundColor Yellow
Get-Process python, node, uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 5

# 2. AVVIO CRYPTO STACK (Binance)
Write-Host "[2/4] Inizializzazione AI-Binance Swarm (Settore Alpha)..." -ForegroundColor Cyan
Start-Process cmd.exe -ArgumentList "/c cd /d h:\ai-binance && .\START_STACK.bat" -WindowStyle Minimized
Start-Sleep -Seconds 10

# 3. AVVIO TRADFI STACK (Gold Sandbox)
Write-Host "[3/4] Inizializzazione AI-TradFi Gold Sandbox (Settore Omega)..." -ForegroundColor Magenta
Start-Process python.exe -ArgumentList "h:\ai-tradfi-parallel\main.py" -WorkingDirectory "h:\ai-tradfi-parallel" -WindowStyle Minimized
Start-Sleep -Seconds 5

# 4. VERIFICA HEALTH CHECK (Porta 8088)
Write-Host "[4/4] Verifica stabilità Cockpit v11..." -ForegroundColor Yellow
$max_attempts = 10
for ($i = 1; $i -le $max_attempts; $i++) {
    $check = Test-NetConnection -ComputerName 127.0.0.1 -Port 8088 -InformationLevel Quiet
    if ($check) {
        Write-Host "`n[SUCCESSO] TUTTI I SISTEMI ONLINE!" -ForegroundColor Green
        Write-Host "Dashboard HUD: http://127.0.0.1:8088/commander" -ForegroundColor Cyan
        break
    }
    Write-Host "Sincronizzazione in corso ($i/$max_attempts)..." -ForegroundColor Gray
    Start-Sleep -Seconds 3
}

if ($i -eq $max_attempts) {
    Write-Host "[WARNING] Il server web è lento. Verifica manualmente su http://127.0.0.1:8088/commander" -ForegroundColor Red
}

Write-Host "`nMISSIONE NOTTURNA ATTIVA. I BOT STANNO EVOLVENDO." -ForegroundColor Green
Write-Host "Premi un tasto per chiudere questo orchestratore (i bot rimarranno attivi)."
Read-Host
