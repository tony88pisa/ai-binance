# ==============================================================================
# AI TRADING PLATFORM V6.0 - DRY RUN LAUNCHER
# Starts the independent research daemon and the freqtrade engine.
# ==============================================================================

Write-Host "Starting AI Trading Platform V6.0 (DRY RUN)" -ForegroundColor Cyan

# 1. Enforce validation mode
$env:VALIDATION_MODE="real"

# 2. Check if venv exists
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Error: Virtual environment not found." -ForegroundColor Red
    exit 1
}

# 3. Stop existing instances
Stop-Process -Name "python","freqtrade" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 4. Start Research Daemon in background
Write-Host "Starting Research Daemon (always-on)..." -ForegroundColor Yellow
Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "-m", "research.daemon" -WindowStyle Minimized

# 5. Start Freqtrade API & Strategy
Write-Host "Starting Freqtrade Strategy (YieldAggregatorAI V6.0)..." -ForegroundColor Green
& .\.venv\Scripts\freqtrade.exe trade --strategy YieldAggregatorAIStrategy -c config.json --dry-run
