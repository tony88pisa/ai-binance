# --- V8.3 CANONICAL STARTUP ---
Write-Host "Inizializzazione Robot Trading V8.3..." -ForegroundColor Cyan

# 1. Ollama
$ollama_proc = Get-Process ollama -ErrorAction SilentlyContinue
if (!$ollama_proc) {
    Write-Host "[1/5] Avvio Ollama Serve..." -ForegroundColor Yellow
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
} else {
    Write-Host "[1/5] Ollama è già attivo." -ForegroundColor Green
}

# 2. Dashboard
Write-Host "[2/6] Avvio Dashboard (Port 8087 - Modulo 11)..." -ForegroundColor Yellow
$dashboard_proc = Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn dashboard.app:app --host 0.0.0.0 --port 8087" -RedirectStandardOutput "logs\dashboard.log" -RedirectStandardError "logs\dashboard_error.log" -WindowStyle Hidden -PassThru

# 2.b Market Daemon (Phase 3 Live updates)
Write-Host "[3/6] Avvio Market Daemon (Dati in tempo reale)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "daemon_market_update.py" -RedirectStandardOutput "logs\daemon.log" -RedirectStandardError "logs\daemon_error.log" -WindowStyle Hidden -PassThru

# 4. Freqtrade (Port 8080)
Write-Host "[4/6] Avvio Freqtrade Engine (START_FREQTRADE.ps1)..." -ForegroundColor Yellow
Start-Process pwsh -ArgumentList "-ExecutionPolicy Bypass -File START_FREQTRADE.ps1" -WindowStyle Hidden

# 5. Evolution Loop
Write-Host "[5/6] Avvio Evolution Loop (NVIDIA Teacher)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "scripts/evolution_loop.py" -RedirectStandardOutput "logs\evolution_loop.log" -RedirectStandardError "logs\evolution_loop_error.log" -WindowStyle Hidden

# 6. Cloudflare Tunnel
Write-Host "[6/6] Avvio Cloudflare Tunnel (HTTPS)..." -ForegroundColor Yellow
$cf_proc = Get-Process cloudflared -ErrorAction SilentlyContinue
if (!$cf_proc) {
    # Usiamo localhost invece di 127.0.0.1 per maggiore compatibilità
    Start-Process ".\cloudflared.exe" -ArgumentList "tunnel --url http://localhost:8087" -RedirectStandardError "logs\cloudflared.log" -WindowStyle Hidden
}

Write-Host "`n--- STACK AVVIATO ---" -ForegroundColor Cyan
Write-Host "Dashboard: http://127.0.0.1:8087"
Write-Host "Cloudflare: https://journalism-episode-podcasts-bite.trycloudflare.com"
