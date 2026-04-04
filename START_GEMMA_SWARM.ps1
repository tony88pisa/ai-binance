# START_GEMMA_SWARM.ps1 - ALPHA SECTOR MASTER ORCHESTRATOR
# Versione 1.0 (Gemma 4 Optimized) - April 2026

Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "   TENGU OS: GEMMA 4 MASTER LAUNCHER (RTX 5080 EDITION)" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan

# 1. PULIZIA E RESET HARDWARE
Write-Host "[1/4] Neutralizzazione processi zombie e sblocco GPU..." -ForegroundColor Yellow
$env:PATH += ";C:\Windows\System32"
taskkill /F /IM ollama* /T /ErrorAction SilentlyContinue 
taskkill /F /IM python* /T /ErrorAction SilentlyContinue
Start-Sleep -Seconds 5

# 2. CONFIGURAZIONE AMBIENTE SSD
Write-Host "[2/4] Inizializzazione Storage SSD (C:\ollama_models)..." -ForegroundColor Green
$env:OLLAMA_MODELS = "C:\ollama_models"
$env:OLLAMA_API_KEY = "529155f7d078482e8b462c2ce3739595._tX2F4lipn8QGnweHBRiITu-"

# Avvio Server Ollama in Background
Write-Host "   -> Accensione Motore AI..." -ForegroundColor Gray
Start-Process "ollama" -ArgumentList "serve" -NoNewWindow
Start-Sleep -Seconds 10

# 3. AVVIO TRADING DASHBOARD (Monitoraggio Real-Time)
Write-Host "[3/4] Lancio Cockpit di Monitoraggio (Porta 8088)..." -ForegroundColor Cyan
Start-Process cmd.exe -ArgumentList "/c cd /d h:\ai-binance && python -m dashboard.app" -WindowStyle Minimized
Start-Sleep -Seconds 5

# 4. AVVIO TRADING SWARM (Binance Sector)
Write-Host "[4/4] Iniezione Strategie Gemma 4 su Binance..." -ForegroundColor Magenta
Start-Process cmd.exe -ArgumentList "/c cd /d h:\ai-binance && python ai/nvidia_client.py" -WindowStyle Minimized

Write-Host "`n[SUCCESSO] TUTTI I SISTEMI ONLINE!" -ForegroundColor Green
Write-Host "Dashboard HUD: http://127.0.0.1:8088/commander" -ForegroundColor Cyan
Write-Host "`nMISSIONE ATTIVA. LA RTX 5080 STA ELABORANDO." -ForegroundColor Green
Write-Host "Premi un tasto per chiudere questo orchestratore (i bot rimarranno attivi)."
Read-Host
