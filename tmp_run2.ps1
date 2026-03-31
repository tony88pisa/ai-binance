Stop-Process -Name python -Force -ErrorAction SilentlyContinue 
Start-Sleep -Seconds 2

New-Item -ItemType Directory -Force "logs"
New-Item -ItemType Directory -Force "storage"

# Inizializza DB esegue table setup e migrazioni (aggiunta entry_price, status chiuso, unicità outcome)
.\.venv\Scripts\python.exe -c "from storage.repository import Repository; Repository()"

# Daemon
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "daemon_market_update.py" -WindowStyle Hidden

# Dashboard
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "-m", "uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8087" -WindowStyle Hidden

Start-Sleep -Seconds 10
Write-Host "--- HEALTH ENDPOINT ---"
Invoke-RestMethod -Uri "http://127.0.0.1:8087/health" -UseBasicParsing | ConvertTo-Json

Write-Host "--- SQLITE QUERIES ---"
.\.venv\Scripts\python.exe -c "
import sqlite3
c = sqlite3.connect('storage/v8_platform.sqlite')
print('MAX(atr_5m) per asset:')
for r in c.execute('SELECT MAX(atr_5m), asset FROM market_data GROUP BY asset;'): print(r)
print('HOLD decisions count =', c.execute('SELECT COUNT(*) FROM decisions WHERE action=''hold'';').fetchone()[0])
print('Outcomes count =', c.execute('SELECT COUNT(*) FROM trade_outcomes;').fetchone()[0])
"

Write-Host "--- DAEMON.LOG (ULTIME 20 RIGHE) ---"
Get-Content -Path "logs\daemon.log" -Tail 20 -ErrorAction SilentlyContinue

Write-Host "--- DAEMON_ERROR.LOG (ULTIME 5 RIGHE) ---"
Get-Content -Path "logs\daemon_error.log" -Tail 5 -ErrorAction SilentlyContinue
