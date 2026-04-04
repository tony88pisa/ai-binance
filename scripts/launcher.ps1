# Tengu OS V10 - Master Orchestration Script (April 2026 Edition)
# ═══════════════════════════════════════════════════════════════════════════════

$ErrorActionPreference = "SilentlyContinue"
$PROJECT_ROOT = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $PROJECT_ROOT

function Write-Host-Colored($msg, $color) {
    Write-Host "[TENGU] $msg" -ForegroundColor $color
}

# 1. DEFINIZIONE PORTE E SERVIZI
$SERVICES = @(
    @{ name="Ollama API";    port=11434; cmd="ollama serve"; type="background" },
    @{ name="WhatsApp MCP";  port=8099;  cmd="node services/whatsapp_mcp/server.js"; type="background" },
    @{ name="Memory Bridge"; port=8098;  cmd="npx -y mcp-remote https://api.supermemory.ai/mcp"; type="background" },
    @{ name="Dashboard V10"; port=8088;  cmd=".venv/Scripts/python.exe dashboard/app.py"; type="background" }
)

$AGENTS = @(
    @{ name="Squad Crypto (Binance)"; cmd=".venv/Scripts/python.exe agents/squad_crypto.py" },
    @{ name="Squad Equity (Stocks)";  cmd=".venv/Scripts/python.exe agents/squad_equity.py" },
    @{ name="News Sentiment Trader";  cmd=".venv/Scripts/python.exe agents/news_trader.py" },
    @{ name="Risk Controller (AI)";   cmd=".venv/Scripts/python.exe agents/risk_controller.py" }
)

# 2. KILL PROCESSI SU PORTE OCCUPATE
Write-Host-Colored "Analisi delle porte e pulizia processi attivi..." "Cyan"

foreach ($svc in $SERVICES) {
    $port = $svc.port
    # Find all processes on this port, excluding the current script's PID or System Idle (PID 0)
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -ne $PID -and $_.OwningProcess -ne 0 }
    if ($connections) {
        $targetPid = $connections[0].OwningProcess
        try {
            $pName = (Get-Process -Id $targetPid).ProcessName
            Write-Host-Colored "Porta $port occupata da $pName (PID: $targetPid). Terminazione in corso..." "Yellow"
            Stop-Process -Id $targetPid -Force -ErrorAction Ignore
            Start-Sleep -Seconds 2
        } catch {
            Write-Host-Colored "Impossibile terminare PID $targetPid. Potrebbe essere un processo di sistema." "Red"
        }
    } else {
        Write-Host-Colored "Porta $port libera o occupata dal launcher stesso." "Green"
    }
}

# 3. AVVIO SERVIZI BASE
Write-Host-Colored "`nAvvio Servizi Infrastruttura..." "Cyan"

foreach ($svc in $SERVICES) {
    Write-Host-Colored "Lancio $($svc.name)..." "Gray"
    if ($svc.type -eq "background") {
        Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -Command $($svc.cmd)" -NoNewWindow
    }
    Start-Sleep -Seconds 3
}

# 4. AVVIO AGENTI AI
Write-Host-Colored "`nIngaggio Swarm d'Elite (Agenti)..." "Cyan"

foreach ($agent in $AGENTS) {
    Write-Host-Colored "Attivazione $($agent.name)..." "Gray"
    Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile -Command $($agent.cmd)" -NoNewWindow
    Start-Sleep -Seconds 2
}

Write-Host-Colored "`n🚀 TUTTI I SISTEMI SONO ONLINE." "Green"
Write-Host-Colored "Dashboard: http://localhost:8088/trader" "White"
Write-Host-Colored "WhatsApp Service: http://localhost:8099/status (Webhook)" "White"

# 5. APERTURA BROWSER (Opzionale, ma consigliato)
Start-Process "http://localhost:8088/trader"

Write-Host-Colored "`nPremi un tasto per chiudere questo launcher (i servizi rimarranno attivi in background)." "Yellow"
Pause
