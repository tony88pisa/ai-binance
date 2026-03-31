# AI Quantitative Trader (V6.0)

Local-first AI trading platform for crypto spot trading.  
Uses Freqtrade as an execution engine + Ollama (`qwen3:8b`) for structured AI decision making.

## Architecture

```
Research Daemon → Context Hash → AI Decision Engine → Risk Gate → Execution (Freqtrade)
```

| Layer | Module | Status |
|---|---|---|
| **Foundations** | `config/`, `ai/types.py` | ✅ Centralized settings, strict JSON schemas |
| **Research** | `research/daemon.py` | ✅ Always-on async market intelligence |
| **Decision** | `ai/decision_engine.py` | ✅ Deterministic multi-stage parsing |
| **Risk Gate** | `risk/gate.py` | ✅ Independent hard-blocks & stake sizing |
| **Memory** | `memory/manager.py` | ✅ Evaluation logging (No machine learning capability) |
| **Validation** | `ai/cache.py`, `scripts/` | ✅ Offline Backtesting tools (Mock/Cached/Real) |

## Quick Start

### Prerequisites
- Python 3.12+
- Ollama with `qwen3:8b` model installed
- NVIDIA GPU (RTX 5080 recommended for sub-3s inference)

### Setup
```bash
# 1. Clone & Setup
git clone <this-repo>
cd ai-binance
python -m venv .venv
.\.venv\Scripts\activate

# 2. Install & Configure
pip install -r requirements.txt
cp .env.example .env

# 3. Start ecosystem (Daemon + Freqtrade)
.\scripts\run_dry_run.ps1
```

### Telemetry Dashboard
- **URL**: http://127.0.0.1:8085 (Bot metrics and validation status)
- **FreqUI**: http://127.0.0.1:8080 (Trading operations)

## Risk & Honesty Disclaimer

This is experimental quantitative software built for research and evaluation. **It does not guarantee profitability.**
The "Memory" module records outcomes for human review; **the AI does not train itself on past trades.** Note that local LMs like qwen3:8b can suffer from contextual drift or hallucinated confidence levels during sideways markets. The system relies heavily on strict mathematical risk gates to limit exposure.

Always validate configurations using `scripts/generate_report.py` in `-Mode mock` before running live. Ensure you monitor the Research Daemon's uptime.
Use strictly at your own financial risk.
