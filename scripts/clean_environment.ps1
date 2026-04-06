# Nuclear Reset for TENGU Environment
Write-Host "[RESET] Killing all Python processes..." -ForegroundColor Cyan
Get-Process python* -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Stop-Process -Id $_.Id -Force
        Write-Host "  - Killed PID: $($_.Id) ($($_.ProcessName))" -ForegroundColor Gray
    } catch {
        Write-Host "  - Failed to kill PID: $($_.Id)" -ForegroundColor Red
    }
}

Write-Host "[RESET] Killing all Node.js processes..." -ForegroundColor Cyan
Get-Process node* -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Stop-Process -Id $_.Id -Force
        Write-Host "  - Killed PID: $($_.Id)" -ForegroundColor Gray
    } catch { }
}

Write-Host "[RESET] Environment clean." -ForegroundColor Green
