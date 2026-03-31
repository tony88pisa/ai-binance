# PROJECT_MEMORY.md — Permanent Project State
# Last Major Update: 2026-03-28 (V6.0 Architecture)

## Project Identity
- **Name**: AI Quantitative Trader (V6.0)
- **Environment**: Freqtrade 2026.2 on Windows + Async Python Daemons
- **Execution Platform**: Bitget (Spot)
- **Primary Assets**: BTC/USDC
- **Strategy**: YieldAggregatorAIStrategy (V6.0)

## The V6.0 Architecture
The system is built on 6 core modules, separating execution from AI inferences to provide structural boundaries around language model hallucinations.

1. **Foundations (`config/`, `ai/types.py`)** 
   - No hardcoded secrets. Environment-driven `settings.py`.
   - `validate_and_report()` runs on `bot_start()` to prevent live configurations with mocking modes or unmapped IP bindings.
2. **Asynchronous Research (`research/daemon.py`)**
   - Headless background worker pulling RSS/Sentiment.
   - Pushes serialized state (`research_state.json`) downstream without degrading Freqtrade's main event loop.
3. **Structured Decision Engine (`ai/decision_engine.py`)**
   - Calls `qwen3:8b` strictly mapping JSON outputs.
   - 4-stage fallback parser resolving `{"decision": "buy|hold", "confidence": int}` directly into dataclasses.
4. **Independent Risk Gate (`risk/gate.py`)**
   - Hard firewall between AI decisions and Exchange API.
   - Intercepts over-confident AI calls, checks circuit breakers, limits max stake %, and forces scale-downs during negative momentum.
5. **Evaluation Memory (`memory/manager.py`)**
   - Replaced legacy text-based "lessons learned" with structured UUID-linked `DecisionRecords` and `OutcomeRecords`.
   - The memory **does not train the model**. It stores evaluations strictly for human auditing via CLI (`generate_report.py`).
6. **Validation & Observability (`ai/cache.py`, `telemetry/`)**
   - Implements 3-Mode Backtesting (`mock`, `cached`, `real`).
   - Hashing layers (`_generate_context_hash`) bind inferences to specific context parameters to allow replaying historical runs.
   - FastAPI dashboard available via `127.0.0.1:8085` detailing validation modes and metric scores.

## Upgrades Post-Qwen3:8b (Roadmap)
When infrastructure allows, target these upgrades:

### 1. Better Local Reasoning Models
- **Llama-3-8B-Instruct / Mistral-Nemo-12B**: Potential drops-ins for tighter JSON adherence if `qwen3` struggles with complex schema validation over time.
- *Note: Do NOT use coding-specialized models (e.g., DeepSeek-Coder-33B) as primary market reasoners unless explicitly finetuned for quantitative logic rules, as their priors optimize for syntax, not market regimes.*

### 2. Better Cloud Reasoning Models
- **Llama-3-70B-Instruct or GPT-4o**: For macro reasoning. Offloading the summarization of 50+ news items or full Fed transcripts to a massive semantic engine, while passing the distilled sentiment to local `qwen3:8b` for execution.

### 3. Optional Adversarial / Verifier Models
- **Phi-3-Mini (Local)**: Deploy a secondary minimalist model acting as an adversary. Prompt: *"The primary model just said BUY. Read its thesis and find the logical fallacy."* Used to filter false confidence.

### 4. Coding / Maintenance Models
- **Qwen2.5-Coder-32B or DeepSeek-Coder-V2**: Dedicated completely to generating `scripts/` or expanding Freqtrade indicator sets during development. Not used for active trading inference.

## Lessons Learned & Truth Vectors
1. Auto-training local LLMs on recent trade outcomes via prompt ingestion is statistically invalid. We separated Memory into a purely observability-focused mechanism.
2. Sub-processing AI calls inside the freqtrade `populate_entry_trend` slows backtesting down by 4,000,000%. Validation Modes (MOCK/CACHED) are functionally mandatory.
3. Language models naturally drift toward 'buy' biases during trending charts. The Risk Gate's math-based circuit breaker is statistically more critical to preserving wallet capital than the LLM's thesis string quality.
