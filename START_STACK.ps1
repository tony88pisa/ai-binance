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
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn dashboard.app:app --host 0.0.0.0 --port 8087" -RedirectStandardOutput "logs\dashboard.log" -RedirectStandardError "logs\dashboard_error.log" -WindowStyle Hidden

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
    Start-Process ".\cloudflared.exe" -ArgumentList "tunnel --url http://localhost:8087" -RedirectStandardError "logs\cloudflared.log" -WindowStyle Hidden
}

# 12. Tengu Desktop Control Center
Write-Host "[12/13] Avvio Tengu Desktop (GUI)..." -ForegroundColor Yellow
# We launch Electron using cmd /c npm.cmd run dev to avoid opening npm.ps1 in an editor
# We explicitly force the directory to H:\ai-binance\tengu-desktop to avoid confusion
Start-Process cmd.exe -ArgumentList "/c npm.cmd run dev" -WorkingDirectory "H:\ai-binance\tengu-desktop" -WindowStyle Hidden

Write-Host "In attesa che il Backend (Port 8087) e la GUI (Port 5173) siano pronti..." -ForegroundColor Magenta

# HEALTH CHECK LOOP: Wait for FastAPI and Vite to be alive
$max_attempts = 15
$attempt = 0
while ($attempt -lt $max_attempts) {
    Start-Sleep -Seconds 3
    $backend_up = (Test-NetConnection 127.0.0.1 -Port 8087 -ErrorAction SilentlyContinue).TcpTestSucceeded
    $gui_up = (Test-NetConnection 127.0.0.1 -Port 5173 -ErrorAction SilentlyContinue).TcpTestSucceeded
    
    if ($backend_up -and $gui_up) {
        Write-Host "[SUCCESSO] Tutti i sistemi sono ONLINE!" -ForegroundColor Green
        break
    }
    $attempt++
    Write-Host "Verifica in corso ($attempt/$max_attempts)... [Backend: $backend_up, GUI: $gui_up]" -ForegroundColor Gray
}

# 13. WhatsApp MCP Server
Write-Host "[13/13] Avvio WhatsApp MCP Server (Node.js)..." -ForegroundColor Yellow
Start-Process "node" -ArgumentList "server.js" -WorkingDirectory "h:\ai-binance\services\whatsapp_mcp" -WindowStyle Hidden

Write-Host "`n--- STACK COMPLETO AVVIATO ---" -ForegroundColor Cyan
Write-Host "Dashboard:     http://127.0.0.1:8087"
Write-Host "WhatsApp MCP:  [Attivo] su http://127.0.0.1:8099"
Write-Host "MCP Server:    http://127.0.0.1:8089/sse"
Write-Host "Coordinator:   Active (ai_memory/project/daily_synthesis.md)"
Write-Host "Dream Agent:   Active (ai_memory/project/current_strategy.md)"
Write-Host "Tengu GUI:     Avviata (Desktop App)"
Write-Host "Cloudflare:    https://journalism-episode-podcasts-bite.trycloudflare.com"
