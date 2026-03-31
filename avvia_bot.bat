@echo off
TITLE AI QUANTITATIVE TRADER V4.0 - SOTA Marzo 2026
color 0A
set ROOT_DIR=%~dp0
cd /d "%ROOT_DIR%"

echo =============================================================
echo     AI QUANTITATIVE TRADER V4.0 (MARZO 2026)
echo     Ollama qwen3:8b + Freqtrade Spot + Fear^&Greed + RAG
echo =============================================================
echo.

echo [0/4] Pulizia vecchi processi...
taskkill /F /IM "freqtrade.exe" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Freqtrade*" /IM "python.exe" >nul 2>&1
timeout /t 3 /nobreak >nul

echo [1/4] Verifica Ollama AI...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [1/4] Ollama AI server e gia attivo.
) else (
    echo [1/4] Avviando Ollama AI server in background...
    start /B ollama serve >nul 2>&1
    timeout /t 8 /nobreak >nul
)

echo [2/4] Patch Sistema FastAPI (Windows Fix)...
powershell -NoProfile -Command "$patchFile = '%ROOT_DIR%.venv\Lib\site-packages\fastapi\dependencies\utils.py'; if (Test-Path $patchFile) { $content = Get-Content $patchFile -Raw; if ($content -match 'assert isinstance\(param_field\.field_info, params\.Body\)') { $content = $content -replace 'assert isinstance\(param_field\.field_info, params\.Body\)', '# assert isinstance(param_field.field_info, params.Body)  # Patched'; Set-Content -Path $patchFile -Value $content; Write-Host '  Patch applicata con successo.' } else { Write-Host '  Patch gia presente.' } }"

echo [3/4] Riscaldamento Modello AI (qwen3:8b) in VRAM...
powershell -NoProfile -Command "try { $body = @{model='qwen3:8b';prompt='warmup';stream=$false;options=@{num_predict=1}} | ConvertTo-Json -Depth 3; Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/generate' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 120 | Out-Null; Write-Host '  Modello caricato in VRAM.' } catch { Write-Host '  ATTENZIONE: Modello non caricato. Verra caricato al primo uso.' }"

echo [4/4] Avvio intelligenza Freqtrade...
echo.
echo =============================================================
echo [ DASHBOARD ]
echo Locale:   http://127.0.0.1:8080
echo Tailscale: http://tony.tail60f7f3.ts.net:8080
echo Username: tony
echo Password: cerundolo
echo =============================================================
echo.

:: Attiva l'ambiente virtuale python e lancia la strategia
call "%ROOT_DIR%.venv\Scripts\activate.bat"
freqtrade trade -c "%ROOT_DIR%config.json" --strategy YieldAggregatorAIStrategy --dry-run --logfile user_data/logs/freqtrade.log

echo.
echo Il bot si e fermato o e andato in crash. Controlla gli errori qui sopra.
pause