# PAPER TRADING OPERATIONS RUNBOOK (V6.0)

This document dictates the strict operational protocol for managing the AI Quantitative Trader during its dry-run evaluation phase. **No real capital is authorized.**

## 1. STARTUP PROCEDURE
1. Verify Windows is awake and power management is set to "Never Sleep".
2. Open PowerShell as Administrator.
3. Verify Ollama is running (`ollama ps` should list no active instances or `qwen3:8b`).
4. Activate the environment: `.\.venv\Scripts\activate`
5. Run the bootstrap script: `.\scripts\run_dry_run.ps1`
6. Open your browser to `http://127.0.0.1:8085` to verify the internal telemetry dashboard validates `Validation Mode: REAL`.
7. Open `http://127.0.0.1:8080` (FreqUI) to ensure the strategy is active and waiting for signals.

## 2. SHUTDOWN PROCEDURE
1. Go to FreqUI (`http://127.0.0.1:8080`), select "Force Exit" on any currently open dry-run trades if immediate capital lockup is a concern.
2. In the active PowerShell window running `run_dry_run.ps1`, press `Ctrl+C`.
3. Verify both `freqtrade.exe` and `python -m research.daemon` have terminated via Task Manager.

## 3. RECOVERY PROCEDURE (Crash / Reboot)
If the machine unexpectedly restarts or a process crashes:
1. Wait for Windows to boot.
2. Ensure internet connectivity is stable.
3. Check `user_data/logs/freqtrade.log` for the exact crash exception.
4. Verify `user_data/research_state.json` exists. If corrupted, delete it; the daemon will recreate it.
5. Execute the **Startup Procedure**. Freqtrade will automatically re-sync the SQLite dry-run database (`tradesv3.dryrun.sqlite`) to resume tracking any trades that were left open.

## 4. HEALTH & PERSISTENCE CHECKS
**Daily Check (09:00 AM)**
- Open PowerShell and execute: `python scripts/check_health.py`
- If output says `[OK] All systems operational`, no further action is required.
- If it says `[FAILED]`, open `user_data/logs/alerts.log` to see which system (Ollama, Daemon, Dashboard, Config) caused the alert.

**State Persistence Verification**
- After a reboot, Freqtrade *must* resume existing trades. Verify this by ensuring `tradesv3.dryrun.sqlite` is never manually deleted.
- Run `python scripts/generate_report.py`. The "Total Trades Executed" should not reset to 0 after an unexpected crash.

## 5. ALERTING RULES (Automated)
The `check_health.py` script automatically monitors and logs these explicit flags:
- 🚨 **Daemon Down**: `research_state.json` file hasn't been modified in > 15 minutes.
- 🚨 **Model Unreachable**: Ollama API is not resolving or model isn't pulled.
- 🚨 **Dashboard Dead**: Telemetry endpoint is failing.
- 🚨 **Config Danger**: `validate_and_report()` triggers a `CRITICAL` vulnerability logic bomb.
*(Note on Repeated Risk Vetoes: Checked weekly via generating the full Trade Report).*

## 6. REVIEW WORKFLOW
### Daily Workflow (15 mins)
- Scan Freqtrade logs for `ERROR` or `Traceback`.
- Check the dashboard for the current Win Rate.
- Document any manual restarts in a local ledger.

### Weekly Workflow (1 hr)
- Run `python scripts/generate_report.py`.
- Evaluate `Avg Confidence (Winners)` vs `Avg Confidence (Losers)`. If they are the same, the model's confidence calibration is broken.
- Backup `memory.json` to an atomic snapshot (e.g., `memory_week1.json`).

## 7. PAPER TRADING CHECKLIST

### First 24 Hours
- [ ] Ensure `python scripts/check_health.py` returns green.
- [ ] Monitor CPU/GPU thermals during the first active Ollama inferences (check freqtrade.log for `decision=buy|hold`).
- [ ] Execute `.\scripts\verify_restart_flow.ps1` natively and confirm it correctly parses existing database state without crashing.
- [ ] Check `generate_report.py` output to confirm evaluation metrics are being recorded.

### First 7 Days
- [ ] Achieve 168 hours of continuous uptime without a memory leak crashing Python.
- [ ] Confirm the Risk Gate has correctly blocked over-confident trades during at least one market downtrend.
- [ ] Confirm FreqUI login tokens do not silently expire and lock you out.

### First 30 Days
- [ ] Generate the final full-month Math Report.
- [ ] Analyze the Win-Rate. If Win-Rate is < 45% and Realized PnL is negative, the strategy fails paper trading. Do not proceed to micro-capital.
- [ ] Identify the exact number of `Timeout` errors experienced by Ollama over ~8,600 inference attempts.
