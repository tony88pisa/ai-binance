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
Invoke-RestMethod -Uri "http://127.0.0.1:8087/health" -UseBasicParsing | ConvertTo-Json

# Log View Tail
Get-Content -Path "logs\daemon.log" -Tail 20
Get-Content -Path "logs\daemon_error.log" -Tail 5
