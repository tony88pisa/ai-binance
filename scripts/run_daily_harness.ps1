# ==============================================================================
# AI TRADING PLATFORM V6.0 - DAILY PAPER-TRADING EXECUTION HARNESS
# Usage: Run every morning at 09:00 locally or via Task Scheduler.
# ==============================================================================

Write-Host "--- MODULE 9 DAILY EXECUTION HARNESS ---" -ForegroundColor Cyan
$Date = Get-Date -Format "yyyy-MM-dd HH:mm"
Write-Host "Execution Time: $Date"

# 1. Automatic Health Checks
Write-Host "`n1. Running Health Diagnostics (Ollama, Daemon, Dashboard, Config)..." -ForegroundColor Yellow
$HealthStatus = .\.venv\Scripts\python.exe scripts/check_health.py 2>&1 | Out-String

if ($LASTEXITCODE -ne 0) {
    Write-Host "🚨 CRITICAL: Health Checks Failed. Output:" -ForegroundColor Red
    Write-Host $HealthStatus
    Write-Host "Action Required: Check user_data/logs/alerts.log before continuing paper trading." -ForegroundColor Red
} else {
    Write-Host "✅ Health Checks Passed." -ForegroundColor Green
}

# 2. Extract telemetry snapshot
Write-Host "`n2. Capturing Daily Snapshot & Trade Metrics..." -ForegroundColor Yellow
$SnapshotStatus = .\.venv\Scripts\python.exe scripts/snapshot.py 2>&1 | Out-String

if ($LASTEXITCODE -ne 0) {
    Write-Host "🚨 Warning: Snapshot capture failed. Output:" -ForegroundColor Red
    Write-Host $SnapshotStatus
} else {
    Write-Host $SnapshotStatus
    Write-Host "✅ Daily Snapshot saved to user_data/logs/daily_snapshot.csv." -ForegroundColor Green
}

Write-Host "`n--- DAILY HARNESS COMPLETE ---" -ForegroundColor Cyan
Write-Host "Operator Task: If PnL is negative and Win-Rate < 45%, refer to the PAPER TRADING POLICY to determine if the 7-day or 30-day Review must trigger a strategy pause." -ForegroundColor Gray
