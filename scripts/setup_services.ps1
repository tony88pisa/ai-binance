# ==============================================================================
# AI TRADING PLATFORM V6.0 - WINDOWS SERVICE ORCHESTRATION (WinSW)
# Clean, robust deployment that avoids file lock issues.
# ==============================================================================
$ErrorActionPreference = "Continue"
$RootPath = "H:\ai binance"
$BinDir = "$RootPath\bin"

if (-not (Test-Path $BinDir)) { New-Item -ItemType Directory -Path $BinDir | Out-Null }

Write-Host "--- MODULE 10: CONFIGURING SERVICES ---" -ForegroundColor Cyan

# 1. Download WinSW if missing
$WinSWUrl = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"
$WinSWPath = "$BinDir\winsw.exe"
if (-not (Test-Path $WinSWPath)) {
    Write-Host ">> Downloading WinSW v2.12.0..." -ForegroundColor Yellow
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $WinSWUrl -OutFile $WinSWPath
    Write-Host ">> WinSW downloaded." -ForegroundColor Green
}

# 2. XML Definitions
$FreqXml = @"
<service>
  <id>V6-Freqtrade</id>
  <name>AI Bot V6.0 - Freqtrade Execution</name>
  <description>Executes the main Freqtrade Trading Engine.</description>
  <executable>"$RootPath\.venv\Scripts\python.exe"</executable>
  <arguments>-m freqtrade trade --strategy YieldAggregatorAIStrategy -c "$RootPath\config.json"</arguments>
  <workingdirectory>$RootPath</workingdirectory>
  <logmode>roll</logmode>
  <onfailure action="restart" delay="15 sec"/>
</service>
"@

$DaemonXml = @"
<service>
  <id>V6-Daemon</id>
  <name>AI Bot V6.0 - Research Daemon</name>
  <description>Background Python async daemon fetching news and signals.</description>
  <executable>"$RootPath\.venv\Scripts\python.exe"</executable>
  <arguments>-m research.daemon</arguments>
  <workingdirectory>$RootPath</workingdirectory>
  <logmode>roll</logmode>
  <onfailure action="restart" delay="15 sec"/>
</service>
"@

$ControlCenterXml = @"
<service>
  <id>V6-ControlCenter</id>
  <name>AI Bot V6.0 - Control Center API</name>
  <description>FastAPI Control Center bridging Telemetry to Tailscale.</description>
  <executable>"$RootPath\.venv\Scripts\python.exe"</executable>
  <arguments>-m uvicorn telemetry.control_center:app --port 8085 --host 100.84.252.107</arguments>
  <workingdirectory>$RootPath</workingdirectory>
  <logmode>roll</logmode>
  <onfailure action="restart" delay="15 sec"/>
  <stopparentprocessfirst>true</stopparentprocessfirst>
</service>
"@

$BotDashboardXml = @"
<service>
  <id>V6-BotDashboard</id>
  <name>AI Bot V6.0 - Bot Progress Dashboard</name>
  <description>Simple Profit/Loss Dashboard for non-experts.</description>
  <executable>"$RootPath\.venv\Scripts\python.exe"</executable>
  <arguments>-m uvicorn telemetry.bot_dashboard:app --port 8086 --host 100.84.252.107</arguments>
  <workingdirectory>$RootPath</workingdirectory>
  <logmode>roll</logmode>
  <onfailure action="restart" delay="15 sec"/>
  <stopparentprocessfirst>true</stopparentprocessfirst>
</service>
"@

# 3. Process each service
foreach ($Svc in @("V6-Freqtrade", "V6-Daemon", "V6-ControlCenter", "V6-BotDashboard")) {
    $ExeFile = "$BinDir\$Svc.exe"
    $XmlFile = "$BinDir\$Svc.xml"
    
    Write-Host "`n>> Processing $Svc..." -ForegroundColor Yellow
    
    # 1. Update XML
    if ($Svc -eq "V6-Freqtrade") { Set-Content -Path $XmlFile -Value $FreqXml }
    if ($Svc -eq "V6-Daemon") { Set-Content -Path $XmlFile -Value $DaemonXml }
    if ($Svc -eq "V6-ControlCenter") { Set-Content -Path $XmlFile -Value $ControlCenterXml }
    if ($Svc -eq "V6-BotDashboard") { Set-Content -Path $XmlFile -Value $BotDashboardXml }
    
    # 2. Copy binary if missing
    if (-not (Test-Path $ExeFile)) {
        Copy-Item $WinSWPath -Destination $ExeFile
    }
    
    # 3. Handle Installation
    $Running = Get-Service -Name $Svc -ErrorAction SilentlyContinue
    if (-not $Running) {
        Write-Host "   Installing $Svc..."
        & $ExeFile install
    }
    
    # 4. Handle Starting
    if ($Running.Status -ne "Running") {
        Write-Host "   Starting $Svc..."
        & $ExeFile start
    } else {
        Write-Host "   $Svc is already running. Refreshing config via restart..."
        & $ExeFile stop
        Start-Sleep -Seconds 2
        & $ExeFile start
    }
}

Write-Host "`n--- SERVICES CONFIGURED ---" -ForegroundColor Cyan
Get-Service V6* | Select Name, Status
