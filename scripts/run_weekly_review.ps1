# ==============================================================================
# AI TRADING PLATFORM V6.0 - WEEKLY PAPER-TRADING REVIEW HARNESS
# Usage: Run every weekend manually to determine Go/No-Go for next 7 days.
# ==============================================================================

Write-Host "--- MODULE 9 WEEKLY REVIEW HARNESS ---" -ForegroundColor Cyan
$Date = Get-Date -Format "yyyy-MM-dd"
Write-Host "Review Date: $Date"

# 0. Check Validation Mode Legitimacy
$ModeCheck = .\.venv\Scripts\python.exe -c "from config.settings import get_settings; print(get_settings().model.validation_mode.lower())"
if ($ModeCheck -ne "real") {
    Write-Host ""
    Write-Host "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" -ForegroundColor Red
    Write-Host "  WARNING: UNOFFICIAL REVIEW DATA" -ForegroundColor Red
    Write-Host "  Current settings dictate Validation Mode: $ModeCheck" -ForegroundColor Red
    Write-Host "  Metrics below DO NOT count toward the 20-trade Micro-Cap Gate." -ForegroundColor Red
    Write-Host "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" -ForegroundColor Red
    Write-Host ""
}

Write-Host "`n1. Summarizing 7-Day Performance Metrics..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe scripts/generate_report.py

# 2. Extract alert frequencies
Write-Host "`n2. Scanning Top System Failure Modes (alerts.log)..." -ForegroundColor Yellow
$AlertFails = [System.Collections.Generic.Dictionary[string,int]]::new()

$AlertFails["Ollama Unreachable"] = 0
$AlertFails["Ollama Mismatch"] = 0
$AlertFails["Dashboard Dead"] = 0
$AlertFails["Research Stale"] = 0
$AlertFails["Config Critical"] = 0

if (Test-Path "user_data/logs/alerts.log") {
    Get-Content "user_data/logs/alerts.log" | ForEach-Object {
        if ($_ -match "Unreachable") { $AlertFails["Ollama Unreachable"]++ }
        if ($_ -match "NOT installed") { $AlertFails["Ollama Mismatch"]++ }
        if ($_ -match "Stale") { $AlertFails["Research Stale"]++ }
        if ($_ -match "Dashboard Unreachable") { $AlertFails["Dashboard Dead"]++ }
        if ($_ -match "Config Danger") { $AlertFails["Config Critical"]++ }
    }

    $AlertFails.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object {
        if ($_.Value -gt 0) {
            Write-Host "- $($_.Key): $($_.Value) isolated events" -ForegroundColor Red
        }
    }
} else {
    Write-Host "- 0 Alerts Logged over tracking period." -ForegroundColor Green
}

Write-Host "`n--- WEEKLY REVIEW COMPLETE ---" -ForegroundColor Cyan
Write-Host "Operator Task: Evaluate Pass/Fail Policy. If Confidence Calibration is 'POOR' or Win Rate < 45%, PAUSE STRATEGY." -ForegroundColor Gray
