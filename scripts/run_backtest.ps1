# ==============================================================================
# AI TRADING PLATFORM V6.0 - BACKTEST LAUNCHER
# Replays historical data without destroying the GPU via mode selection.
# ==============================================================================

param (
    [ValidateSet("mock","cached","real")]
    [string]$Mode = "mock"
)

Write-Host "Starting AI Trading Platform V6.0 (BACKTEST - $Mode mode)" -ForegroundColor Cyan

# 1. Enforce validation mode
$env:VALIDATION_MODE=$Mode

# 2. Start Freqtrade API & Strategy
Write-Host "Running Freqtrade Backtest for the last 30 days..." -ForegroundColor Green

# NOTE: Freqtrade by default uses backtest history.
# For long AI runs, "mock" returns fast deterministic trades.
# "cached" reuses exact past model returns based on Technical Context Hashing.
# "real" forces full inference (Warning: extremely slow for backtests).

& .\.venv\Scripts\freqtrade.exe backtesting --strategy YieldAggregatorAIStrategy -c config.json --timerange="$(Get-Date (Get-Date).AddDays(-30) -Format 'yyyyMMdd')-"

Write-Host "`nTo view AI validation results, run:`npython scripts/generate_report.py" -ForegroundColor Yellow
