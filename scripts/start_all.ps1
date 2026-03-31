# V8.1.1 Multi-Service Launcher (NO-DOCKER)
Write-Host "🟢 Starting V8.1.1 AI Platform (Local Mode)..." -ForegroundColor Green

# Ensure Ollama is running
$ollama = Get-Process ollama -ErrorAction SilentlyContinue
if ($null -eq $ollama) {
    Write-Host "1. Starting Ollama..."
    Start-Process "ollama" "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Write-Host "   [OK] Ollama started." -ForegroundColor Green
} else {
    Write-Host "1. Ollama already running." -ForegroundColor Green
}

# Start Services
Write-Host "2. Starting Dashboard (Port 8080)..."
Start-Service V8-Dashboard -ErrorAction SilentlyContinue

Write-Host "3. Starting TestLab Loop..."
Start-Service V8-TestLab -ErrorAction SilentlyContinue

Write-Host "4. Starting Live Guard..."
Start-Service V8-LiveGuard -ErrorAction SilentlyContinue

# Status Check
Write-Host ""
Write-Host "--- SERVICE STATUS ---" -ForegroundColor Cyan
Get-Service V8-* -ErrorAction SilentlyContinue | Select-Object Name, Status

# Network info
$localIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.PrefixOrigin -eq "Dhcp" } | Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "Dashboard PC:     http://localhost:8080" -ForegroundColor Cyan
if (-not [string]::IsNullOrEmpty($localIP)) {
    Write-Host "Dashboard Mobile: http://${localIP}:8080" -ForegroundColor Cyan
}
Write-Host "Done." -ForegroundColor Green
