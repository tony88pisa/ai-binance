@echo off
title V8.1.1 AI TRADING PLATFORM - UNIFIED LAUNCHER
echo ==========================================
echo Starting V8.1.1 AI Platform...
echo ==========================================

REM Robust PowerShell Resolver (pwsh -> powershell)
set "PS_CMD=pwsh"
echo | %PS_CMD% -Version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] pwsh not found. Trying powershell...
    set "PS_CMD=powershell"
    echo | %PS_CMD% -Version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [CRITICAL] PowerShell not found. Please install PowerShell 7 or use Windows PowerShell.
        pause
        exit /b 1
    )
)

echo [READY] Using %PS_CMD%. Executing launcher...
%PS_CMD% -NoProfile -ExecutionPolicy Bypass -File "%~dp0\START_AI_TRADING.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Launcher PS1 failed with code %ERRORLEVEL%.
    pause
) else (
    echo [SUCCESS] Platform initialization triggered.
)
