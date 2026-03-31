# ==============================================================================
# AI QUANTITATIVE TRADER V4.0 — SOTA Marzo 2026
# Ollama qwen3:8b + Freqtrade Spot + Fear&Greed + Memoria RAG
# ==============================================================================
$ROOT_DIR = "H:\ai binance"
Set-Location -Path $ROOT_DIR

Write-Host "=========================================" -ForegroundColor Green
Write-Host "   AI QUANTITATIVE TRADER V4.0"          -ForegroundColor Green
Write-Host "   Ollama + Freqtrade + RAG Memory"       -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green

# ---- STEP 0: Pulizia processi orfani ----
Write-Host "[0/4] Pulizia..." -ForegroundColor Gray
Stop-Process -Name "freqtrade" -Force -ErrorAction SilentlyContinue
Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "*ai binance*" } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

# ---- STEP 1: Ollama ----
$ollamaRunning = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if (-not $ollamaRunning) {
    Write-Host "[1/4] Avvio Ollama..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 8
}
Write-Host "[1/4] Ollama OK" -ForegroundColor Green

# ---- STEP 2: Warm-up modello in VRAM ----
Write-Host "[2/4] Caricamento modello qwen3:8b in VRAM..." -ForegroundColor Yellow
try {
    $body = @{ model = "qwen3:8b"; prompt = "warmup"; stream = $false; options = @{ num_predict = 1 } } | ConvertTo-Json -Depth 3
    Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/generate" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 120 > $null
    Write-Host "[2/4] Modello caricato in VRAM" -ForegroundColor Green
} catch {
    Write-Host "[2/4] ATTENZIONE: Modello non caricato. Verra caricato al primo uso." -ForegroundColor Red
}

# ---- STEP 3: Patch FastAPI (necessaria per Freqtrade su Windows) ----
$patchFile = "$ROOT_DIR\.venv\Lib\site-packages\fastapi\dependencies\utils.py"
if (Test-Path $patchFile) {
    $content = Get-Content $patchFile -Raw
    if ($content -match 'assert isinstance\(param_field\.field_info, params\.Body\)') {
        $content = $content -replace 'assert isinstance\(param_field\.field_info, params\.Body\)', '# assert isinstance(param_field.field_info, params.Body)  # Patched'
        Set-Content -Path $patchFile -Value $content
        Write-Host "[3/4] Patch FastAPI applicata" -ForegroundColor Green
    } else {
        Write-Host "[3/4] Patch FastAPI gia presente" -ForegroundColor Green
    }
}

# ---- STEP 4: Freqtrade ----
Write-Host ""
Write-Host "Dashboard Locale:    http://127.0.0.1:8080" -ForegroundColor Cyan
Write-Host "Dashboard Tailscale: http://tony.tail60f7f3.ts.net:8080" -ForegroundColor Cyan
Write-Host "Login: tony / cerundolo" -ForegroundColor Gray
Write-Host ""
Write-Host "[4/4] Avvio bot..." -ForegroundColor Green

. "$ROOT_DIR\.venv\Scripts\Activate.ps1"
& "$ROOT_DIR\.venv\Scripts\freqtrade.exe" trade -c "$ROOT_DIR\config.json" --strategy YieldAggregatorAIStrategy --dry-run --logfile user_data/logs/freqtrade.log
