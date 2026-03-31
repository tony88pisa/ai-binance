"""
Health Check & Alerting Script for V6.0 Paper Trading.
Run: python scripts/check_health.py

Automates:
- Ollama availability
- Dashboard reachability
- Research staleness
- Config danger detection
"""
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
except ImportError:
    print("CRITICAL: requests module not found. Run pip install requests.")
    sys.exit(1)

from config.settings import get_settings
from config.validator import validate_config, Severity

alerts_log_path = Path("user_data/logs/alerts.log")
alerts_log_path.parent.mkdir(parents=True, exist_ok=True)

# Set up dedicated alert logger
alert_logger = logging.getLogger("health_alerts")
alert_logger.setLevel(logging.WARNING)
handler = logging.FileHandler(alerts_log_path, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
alert_logger.addHandler(handler)

def emit_alert(msg: str, is_critical: bool = False):
    """Outputs alert to console and appends to local alert file. Placeholder for Telegram hook."""
    print(f"[{'CRITICAL' if is_critical else 'WARNING'}] {msg}")
    if is_critical:
        alert_logger.critical(msg)
    else:
        alert_logger.warning(msg)

def check_ollama():
    """Verify Ollama model is installed, loaded, and actively responding."""
    settings = get_settings()
    model = settings.model.model_name
    
    # 1. Is it installed?
    try:
        res = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        res.raise_for_status()
        models = [m.get("name") for m in res.json().get("models", [])]
        if model not in models:
            emit_alert(f"Ollama running, but model '{model}' is NOT installed.", True)
            return False
        print(f"  [+] Model {model} is installed.")
    except Exception as e:
        emit_alert(f"Ollama API Unreachable: {e}", True)
        return False

    # 2. Is it actively resident (loaded)?
    try:
        res_ps = requests.get("http://127.0.0.1:11434/api/ps", timeout=3)
        res_ps.raise_for_status()
        loaded = [m.get("name") for m in res_ps.json().get("models", [])]
        if model not in loaded:
            print(f"  [!] Model {model} is not currently in VRAM (will cold-boot on first request).")
        else:
            print(f"  [+] Model {model} is active in VRAM.")
    except Exception as e:
        pass # Not critical if /api/ps is unavailable in older ollama versions

    # 3. Can it respond quickly? (Active ping)
    try:
        start_t = time.time()
        ping_res = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={"model": model, "prompt": "a", "stream": False, "keep_alive": "5m"},
            timeout=15
        )
        ping_res.raise_for_status()
        latency = (time.time() - start_t) * 1000
        print(f"  [+] Inference ping successful ({latency:.0f} ms).")
        return True
    except Exception as e:
        emit_alert(f"Ollama Model Unresponsive (Inference Ping Failed): {e}", True)
        return False

def check_dashboard():
    """Verify telemetry dashboard is alive."""
    try:
        res = requests.get("http://localhost:8085/api/evaluation", timeout=3)
        res.raise_for_status()
        return True
    except Exception as e:
        emit_alert(f"Telemetry Dashboard Unreachable: {e}", False)
        return False

def check_research_staleness():
    """Verify research_state.json exists and is fresh (< 15 mins)."""
    state_file = Path("user_data/research_state.json")
    if not state_file.exists():
        emit_alert("Research Daemon Down: research_state.json not found.", True)
        return False
    
    mtime = state_file.stat().st_mtime
    age_minutes = (time.time() - mtime) / 60
    if age_minutes > 15:
        emit_alert(f"Stale Research Detected: File is {age_minutes:.1f} minutes old.", True)
        return False
    return True

def check_config_danger():
    """Run programmatic validator check."""
    from config.validator import validate_config
    settings = get_settings()
    issues = validate_config(settings.paths.config_file)
    criticals = [i for i in issues if i.severity == Severity.CRITICAL]
    if criticals:
        for c in criticals:
            emit_alert(f"Config Danger: {c.message}", True)
        return False
    return True

def main():
    print("--- V6.0 HEALTH & ALERT CHECK ---")
    healthy = True
    
    if not check_config_danger(): healthy = False
    if not check_ollama(): healthy = False
    if not check_research_staleness(): healthy = False
    if not check_dashboard(): healthy = False
    
    if healthy:
        print("[OK] All systems operational. State passes 100% paper trading checks.")
        sys.exit(0)
    else:
        print("\n[FAILED] One or more critical systems are failing or stale.")
        print("Check user_data/logs/alerts.log and fix errors.")
        sys.exit(1)

if __name__ == "__main__":
    main()
