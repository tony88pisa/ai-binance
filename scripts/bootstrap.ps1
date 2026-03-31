# V8.1.1 Bootstrap - NO-DOCKER Local Mode
Write-Host "🚀 Starting V8.1.1 Bootstrap (Local-Only)..." -ForegroundColor Cyan

$root = "H:\ai binance"
Set-Location $root

# 1. Initialize SQLite Database
Write-Host "Step 1: Initializing SQLite V8.1.1 Storage..."
python -c "from storage.repository import Repository; Repository()"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Database ready." -ForegroundColor Green
} else {
    Write-Host "  [WARN] DB init returned non-zero. Check Python/storage." -ForegroundColor Yellow
}

# 2. Check Ollama (Local LLM inference)
Write-Host "Step 2: Checking Ollama..."
$ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
if ($null -eq $ollamaProc) {
    Write-Host "  > Starting Ollama serve..." -ForegroundColor Gray
    Start-Process "ollama" "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}
$ollamaVersion = & ollama --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Ollama: $ollamaVersion" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Ollama not found. Install from https://ollama.com" -ForegroundColor Yellow
}

# 3. Registering WinSW Services
Write-Host "Step 3: Registering V8.1.1 Services via WinSW..."
$services = @("V8-Dashboard", "V8-TestLab", "V8-LiveGuard")

foreach ($s in $services) {
    $existing = Get-Service $s -ErrorAction SilentlyContinue
    if ($null -ne $existing) {
        Write-Host "  [OK] $s already registered." -ForegroundColor Green
        continue
    }
    if (Test-Path "bin\winsw.exe") {
        Write-Host "  Installing $s..."
        Copy-Item "bin\winsw.exe" "bin\$s.exe" -Force
        Start-Process -FilePath "bin\$s.exe" -ArgumentList "install" -Wait -NoNewWindow
    } else {
        Write-Host "  [SKIP] bin\winsw.exe not found. Manual service registration required." -ForegroundColor Yellow
    }
}

# 4. Training Status
Write-Host ""
Write-Host "Step 4: Training Status" -ForegroundColor Cyan
Write-Host "  Unsloth GPU training: DISABLED (requires Linux/WSL)" -ForegroundColor Yellow
Write-Host "  The bot operates fully via Ollama local inference." -ForegroundColor Gray
Write-Host "  Training can be done manually in WSL when needed." -ForegroundColor Gray

Write-Host ""
Write-Host "✅ Bootstrap V8.1.1 COMPLETE (NO-DOCKER MODE)." -ForegroundColor Green
