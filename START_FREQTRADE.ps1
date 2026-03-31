<#
.SYNOPSIS
Script di avvio per Freqtrade Ibrido. Legge automaticamente i secret dal file .env per proteggere il config.json
#>

Write-Host "==================================" -ForegroundColor Cyan
Write-Host " AVVIO FREQTRADE AI IBRIDO (SEGURO)" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

$EnvFile = ".\.env"

if (Test-Path $EnvFile) {
    Write-Host "Caricamento variabili d'ambiente da .env..." -ForegroundColor Green
    Get-Content $EnvFile | Where-Object { $_ -match "^[\w_]+=" } | ForEach-Object {
        # Split sulla prima occorrenza di =
        $name, $value = $_ -split '=', 2
        # Rimuove le virgolette doppie o singole dal valore se presenti
        $value = $value -replace '^"(.*)"$','$1' -replace "^'(.*)'$",'$1'
        Set-Item -Path "Env:$name" -Value $value
    }
} else {
    Write-Host "ATTENZIONE: File .env non trovato. Le API potrebbero non autenticarsi." -ForegroundColor Yellow
}

Write-Host "Avvio motore di trading..." -ForegroundColor Cyan
$env:PYTHONUNBUFFERED=1

# Avvia l'eseguibile di Freqtrade
& .\.venv\Scripts\freqtrade.exe trade --strategy OllamaHybridStrategy -c .\config.json --logfile user_data/logs/freqtrade.log
