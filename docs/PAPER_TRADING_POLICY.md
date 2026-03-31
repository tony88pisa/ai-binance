# PAPER TRADING POLICY & MICRO-CAPITAL GATES

This document governs the strict 7–30 day execution evaluation of the `YieldAggregatorAIStrategy` (V6.0). **At no point during this phase is live trading authorized.** 

## 1. SNAPSHOT LOG DESIGN
Every morning, `scripts/run_daily_harness.ps1` executes health checks and pushes operational state to `user_data/logs/daily_snapshot.csv`.  

**Data Captured:**
- `date_time`: Execution timestamp.
- `validation_mode`: Must be `REAL`.
- `current_latency_ms`: Point-in-time inference latency of `qwen3:8b`.
- `stale_events_today`: Daemon down-time.
- `timeouts_today`: Ollama unreachable events.
- `risk_vetoes`: Trades blocked by the mathematical risk firewall.
- `total_decisions` / `executed_trades`: Raw bot volume mapping.
- `open_trades`: State persistence mapped against the SQLite dry-run DB.
- `realized_pnl_pct`: Raw performance metric.

## 2. WEEKLY REVIEW REPORT
Every weekend, execute `scripts/run_weekly_review.ps1`.
This integrates the mathematical confidence calibration report (`generate_report.py`) against `alerts.log` to output the **Top Failure Modes** (Ollama disconnects, Stale Research APIs).  

You must compare:
1. **Win Rate vs PnL**: Strategy profit expectation.
2. **Confidence Calibration (Winners vs. Losers)**: Does `qwen3:8b` reliably score winning trades with >80 confidence, or is confidence completely disconnected from mathematical reality?
3. **Daemon Uptime Issues**: Tracking background crashes on Windows.

## 3. PASS / FAIL POLICY (Strict Limits)

### When to CONTINUE Paper Trading:
- **Sample Size**: Must maintain a statistically relevant velocity (e.g. >3 trades/week).
- **Win Rate**: >= 51%.
- **Realized PnL**: Total return remains structurally positive after rolling drawdowns.
- **Max Drawdown**: Must not exceed 10% of the simulated dry-run starting capital.
- **Risk Gate Block Rate**: Active but < 95% (proving the AI isn't entirely disconnected from math).
- **Timeout Rate**: Ollama disconnects account for < 1% of total inferences.
- **Operational Stability**: Zero memory leaks causing daemon crashes.

### When to PAUSE Paper Trading (Investigate):
- **Confidence Calibration**: Reports "POOR" (i.e. Losers are frequently recommended with 85+ confidence).
- **Analysis Clustering**: `generate_report.py` shows heavy clustering of losses in a specific regime (e.g. `chop`).
- **Instability**: Daemon fails to update `research_state.json` more than 3 times a week.

### When to REJECT the Strategy (No Live Trading permitted):
- **Win Rate Collapse**: Realized Win Rate drops < 45% over a statistically significant 30-day baseline.
- **PnL Deficit**: Realized PnL is entirely negative after a minimum 20 executed trades threshold.
- **Maximum Drawdown**: Realized drawdown exceeds 15% of the portfolio.
- **State Corruption**: Freqtrade SQLite database fails to accurately recover state after an organic reboot.

## 4. MICRO-CAPITAL GATE CRITERIA
Before enabling `dry_run = false` for live capital (€50), you **MUST** mathematically clear these 5 gates. 
*CRITICAL NOTE 1*: Achieving a 20-trade baseline is strictly a minimum screening threshold; it is NOT standalone sufficient evidence to deploy capital if any other gate fails. 
*CRITICAL NOTE 2*: ONLY metrics logged under `validation_mode: operational_real` in the daily snapshots count toward these gates. `mock_validation` and `cached_validation` are completely disqualified from Live authorization.

1. **168hr Rolling Stability**: Zero Python memory leaks or daemon crashes natively on Windows during a continuous 7-day window.
2. **Statistically Viable PnL Check**: A minimum sample size of 20 dry-run completed trades registering mathematically positive PnL and < 10% maximum drawdown.
3. **Slippage Accounting**: Prove that the recorded dry-run fill prices (which assume 0 depth constraint) would have reasonably filled on the Live Orderbook given the 5-minute volatility.
4. **VRAM Stability**: `qwen3:8b` did not OOM (Out-of-Memory) crash across intense multi-thread usage during peak API hours.
5. **Telegram Hook Active**: `config.json` Telegram Webhook is actively broadcasting `buy/sell` events to your mobile device, ensuring emergency halt capability.
