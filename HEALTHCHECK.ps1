# --- V8.3 HEALTHCHECK ---
Write-Host "Verifica Integrità Sistema V8.3..." -ForegroundColor Cyan

# 1. Ports
$ports = @(8086, 8080)
foreach ($p in $ports) {
    if (Test-NetConnection -ComputerName 127.0.0.1 -Port $p -ErrorAction SilentlyContinue | Where-Object { $_.TcpTestSucceeded -eq $true }) {
        Write-Host "[OK] Port $p è in ascolto." -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Port $p NON è in ascolto." -ForegroundColor Red
    }
}

# 2. Ollama
$ollama = Get-Process ollama -ErrorAction SilentlyContinue
if ($ollama) {
    Write-Host "[OK] Ollama è attivo (ID: $($ollama[0].Id))." -ForegroundColor Green
} else {
    Write-Host "[FAIL] Ollama è offline." -ForegroundColor Red
}

# 3. Cloudflare
$cf = Get-Process cloudflared -ErrorAction SilentlyContinue
if ($cf) {
    Write-Host "[OK] Cloudflare Tunnel attivo." -ForegroundColor Green
} else {
    Write-Host "[FAIL] Cloudflare Tunnel arrestato." -ForegroundColor Red
}

# 4. Python Monitoring
$py_procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' AND CommandLine LIKE '%ai binance%'"
if ($py_procs) {
    Write-Host "[OK] $($py_procs.Count) processi Python (Dashboard/Evolution/Watcher) attivi." -ForegroundColor Green
} else {
    Write-Host "[FAIL] Nessun processo Python di controllo attivo." -ForegroundColor Red
}

Write-Host "-------------------------------" -ForegroundColor Cyan
