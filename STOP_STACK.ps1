# --- V8.3 STOP STACK ---
Write-Host "Arresto di emergenza in corso..." -ForegroundColor Red

# Stop Freqtrade
Get-Process freqtrade -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "[X] Freqtrade arrestato." -ForegroundColor DarkGray

# Stop Python child processes (Evolution, Dashboard, Watcher)
# Identifica i processi python lanciati dalla nostra directory
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' AND CommandLine LIKE '%ai binance%'" | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "[X] Processo Python ID $($_.ProcessId) terminato." -ForegroundColor DarkGray
}

# Stop Node (WhatsApp MCP)
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "[X] WhatsApp MCP (Node) terminato." -ForegroundColor DarkGray

# Stop Cloudflare
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "[X] Cloudflare Tunnel chiuso." -ForegroundColor DarkGray

Write-Host "--- STACK FERMO ---" -ForegroundColor Red

