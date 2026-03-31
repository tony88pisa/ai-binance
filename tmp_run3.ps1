Stop-Process -Name python -Force -ErrorAction SilentlyContinue 
Start-Sleep -Seconds 2

Remove-Item -Path "logs\daemon.log" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "logs\daemon_error.log" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

Write-Host "--- CLEAN DB AND MIGRATE ---"
.\.venv\Scripts\python.exe tmp_setup.py

Write-Host "--- STARTING SERVICES ---"
# Daemon
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "daemon_market_update.py" -WindowStyle Hidden

# Dashboard (Force 0.0.0.0 for mobile access)
Start-Process ".\.venv\Scripts\python.exe" -ArgumentList "-m uvicorn dashboard.app:app --host 0.0.0.0 --port 8087" -RedirectStandardOutput "logs\dashboard.log" -RedirectStandardError "logs\dashboard_error.log" -WindowStyle Hidden -PassThru

# Cloudflare (Restart if needed)
Write-Host "--- RE-SYNCHRONIZING EXTERNAL LINK (S25) ---"
Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue
Start-Process ".\cloudflared.exe" -ArgumentList "tunnel --url http://127.0.0.1:8087" -RedirectStandardError "logs\cloudflared.log" -WindowStyle Hidden
Start-Sleep -Seconds 5

Write-Host "--- WAITING FOR STARTUP ---"
Start-Sleep -Seconds 10

Write-Host "`n--- ACCESS FROM S25 (MOBILE) ---"
$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -match "Ethernet|Wi-Fi" -and $_.IPAddress -notmatch "172|169|127" }).IPAddress | Select-Object -First 1
$cf_url = Get-Content "logs\cloudflared.log" -Tail 100 | Select-String "trycloudflare.com" | ForEach-Object { $_.ToString().Split('|')[1].Trim() } | Select-Object -Last 1

Write-Host "Local Link: http://$($ip):8087" -ForegroundColor Green
Write-Host "External Link: $($cf_url)" -ForegroundColor Yellow

