# --- V10 MULTI-AGENT STARTUP ---
Write-Host "Inizializzazione Robot Trading V10 (Multi-Agent)..." -ForegroundColor Cyan

# 1. Ollama
$ollama_proc = Get-Process ollama -ErrorAction SilentlyContinue
if (!$ollama_proc) {
    Write-Host "[1/12] Avvio Ollama Serve..." -ForegroundColor Yellow
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
} else {
    Write-Host "[1/12] Ollama è già attivo." -ForegroundColor Green
}

# 2. Dashboard
Write-Host "[2/12] Avvio Dashboard (Port 8087)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn dashboard.app:app --host 0.0.0.0 --port 8088" -RedirectStandardOutput "logs\dashboard.log" -RedirectStandardError "logs\dashboard_error.log" -WindowStyle Hidden

# 3. Binance Executor Agent
Write-Host "[3/12] Avvio Execution Agent (Incrocio Live & Stop)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "agents/binance_executor.py" -WindowStyle Hidden

# 4. Freqtrade (Port 8080)
Write-Host "[4/12] Avvio Freqtrade Engine..." -ForegroundColor Yellow
Start-Process pwsh -ArgumentList "-ExecutionPolicy Bypass -File START_FREQTRADE.ps1" -WindowStyle Hidden

# 5. Risk Controller Agent
Write-Host "[5/12] Avvio Risk Controller (NVIDIA NIM)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "agents/risk_controller.py" -WindowStyle Hidden

# 6. Market Analyzer Agent
Write-Host "[6/12] Avvio Market Analyzer (NVIDIA Decisions)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "agents/market_analyzer.py" -WindowStyle Hidden

# 6b. Equity Background Daemon
Write-Host "[6.5] Avvio Equity Daemon (Yahoo Finance)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "services/equity_daemon.py" -WindowStyle Hidden

# 7. Evolution Loop
Write-Host "[7/12] Avvio Evolution Loop (NVIDIA Teacher)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "scripts/evolution_loop.py" -RedirectStandardOutput "logs\evolution_loop.log" -RedirectStandardError "logs\evolution_loop_error.log" -WindowStyle Hidden

# 7B. HEDGE FUND EXTENSIONS (2026 Testnet)
Write-Host "[7.1] Avvio Flash News Trader (Sentiment Engine)..." -ForegroundColor Magenta
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "agents/news_trader.py" -WindowStyle Hidden
Write-Host "[7.2] Avvio DeFi Yield Farmer (Idle USD Vault)..." -ForegroundColor Magenta
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "agents/defi_farmer.py" -WindowStyle Hidden
Write-Host "[7.3] Avvio Arbitrage Agent (Delta Neutral Future)..." -ForegroundColor Magenta
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "agents/arbitrage_arb.py" -WindowStyle Hidden

# 8. MCP Server (Port 8089)
Write-Host "[8/12] Avvio MCP Server (Model Context Protocol)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "services/mcp_server.py" -WindowStyle Hidden

# 9. Coordinator Agent
Write-Host "[9/12] Avvio Coordinator Agent (Global Oversight)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "agents/coordinator.py" -WindowStyle Hidden

# 10. Dream Agent
Write-Host "[10/12] Avvio Dream Agent (Memory Consolidation)..." -ForegroundColor Yellow
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "agents/dream_agent.py" -WindowStyle Hidden

# 11. Cloudflare Tunnel
Write-Host "[11/12] Avvio Cloudflare Tunnel (HTTPS)..." -ForegroundColor Yellow
$cf_proc = Get-Process cloudflared -ErrorAction SilentlyContinue
if (!$cf_proc) {
    Start-Process ".\cloudflared.exe" -ArgumentList "tunnel --url http://localhost:8088" -RedirectStandardError "logs\cloudflared.log" -WindowStyle Hidden
}

# 12. Tengu Alpha Web Dashboard
Write-Host "[12/12] Avvio Tengu Alpha Arena (Web HUD)..." -ForegroundColor Yellow
# We no longer launch Electron. The FastAPI server handles the static build.

Write-Host "In attesa che il Centro di Comando Web (Port 8088) sia pronto..." -ForegroundColor Magenta

# HEALTH CHECK LOOP: Wait for FastAPI
$max_attempts = 15
$attempt = 0
while ($attempt -lt $max_attempts) {
    Start-Sleep -Seconds 3
    $backend_up = (Test-NetConnection 127.0.0.1 -Port 8088 -ErrorAction SilentlyContinue).TcpTestSucceeded
    
    if ($backend_up) {
        Write-Host "[SUCCESSO] Centro di Comando ONLINE!" -ForegroundColor Green
        break
    }
    $attempt++
    Write-Host "Verifica in corso ($attempt/$max_attempts)... [Web Server: $backend_up]" -ForegroundColor Gray
}

Write-Host "`n--- TENGU COMMANDER COCKPIT ---" -ForegroundColor Cyan
Write-Host "Dashboard HUD: http://127.0.0.1:8088/commander"
Write-Host "WhatsApp MCP:  [Attivo] su http://127.0.0.1:8099"
Write-Host "MCP Server:    http://127.0.0.1:8089/sse"
Write-Host "Coordinator:   Active (ai_memory/project/daily_synthesis.md)"
Write-Host "Dream Agent:   Active (ai_memory/project/current_strategy.md)"

if ($attempt -eq $max_attempts) {
    Write-Host "[ATTENZIONE] Il server web potrebbe essere lento ad avviarsi sulla porta 8088. Se non carica, riprova tra pochi secondi." -ForegroundColor Yellow
}

Write-Host "`n[SUCCESSO] Inizializzazione completata." -ForegroundColor Green
Write-Host "Apri il browser su: http://127.0.0.1:8088/commander" -ForegroundColor Cyan
Write-Host "Premi un tasto per chiudere questa finestra o lasciala aperta."
Read-Host
