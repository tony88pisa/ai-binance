"""
TENGU V11.5 — COORDINATOR (FIXED)
=====================================
Fix applicati:
  [FIX-A] PROJECT_ROOT definito prima di get_settings() (era invertito).
  [FIX-B] Rimosso repo.get_history() inesistente — sostituito con query diretta.
  [FIX-C] Heartbeat parsing: gestito fromisoformat() con timezone-aware check.
  [FIX-D] Auto-resume circuit breaker: non riattiva se emergency_stop fu settato
          manualmente dall'utente (controlla ai_reasoning prefix).
  [FIX-E] generate_synthesis: rimosso repo.get_history(), usa query diretta.
  [FIX-F] Loop principale usa schedule invece di time.sleep fisso.
"""
import sys
import time
import json
import logging
import os
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

import schedule
from dotenv import load_dotenv

# [FIX-A] PROJECT_ROOT definito PRIMA di qualsiasi import locale
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

from config.settings import get_settings
from storage.repository import Repository
from storage.memory_manager import MemoryManager
from telemetry.cost_tracker import get_cost_tracker
from modules.notifications_hub import NotificationsHub

settings = get_settings()

# ── Logging ─────────────────────────────────────────────────────────────────
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [COORDINATOR] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "coordinator.log", encoding="utf-8", delay=True),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("coordinator")

REPORT_MIN_INTERVAL_HOURS = 4
AGENTS_TO_WATCH = ["squad_crypto", "squad_equity", "news_trader", "dream_agent"]
HEARTBEAT_STALE_MINUTES = 15


class Coordinator:
    """
    Top-level Orchestrator Agent V11.5.
    Monitora gli agenti tramite heartbeat, gestisce circuit breaker globale
    e genera report giornalieri tramite NVIDIA LLM.
    """

    def __init__(self):
        self.repo = Repository()
        self.mm = MemoryManager(str(PROJECT_ROOT))
        self.tracker = get_cost_tracker(str(PROJECT_ROOT))
        self.daily_budget_limit = float(os.getenv("AI_DAILY_BUDGET", "2.00"))
        self.notifier = NotificationsHub()

    # ── Health Check [FIX-C] ───────────────────────────────────────────────

    def get_system_health(self) -> dict:
        """Controlla se gli agenti sono attivi via heartbeat."""
        health = {}
        now_utc = datetime.now(timezone.utc)

        for agent in AGENTS_TO_WATCH:
            state = self.repo.get_service_state(agent)
            hb_str = state.get("last_heartbeat")
            if not hb_str:
                health[agent] = "MISSING"
                continue
            try:
                # [FIX-C] Gestione timezone-aware / naive
                hb_time = datetime.fromisoformat(hb_str)
                if hb_time.tzinfo is None:
                    hb_time = hb_time.replace(tzinfo=timezone.utc)
                delta = now_utc - hb_time
                health[agent] = "OK" if delta < timedelta(minutes=HEARTBEAT_STALE_MINUTES) else "STALE"
            except (ValueError, TypeError) as e:
                logger.warning(f"Heartbeat parse error per {agent}: {e}")
                health[agent] = "PARSE_ERROR"

        return health

    # ── Circuit Breakers [FIX-D] ────────────────────────────────────────────

    def check_circuit_breakers(self, health: dict, costs: dict) -> None:
        """
        Attiva emergency_stop se costi o agenti sono critici.
        [FIX-D] Auto-resume NON sblocca se emergency_stop fu settato manualmente
        (ai_reasoning non inizia con "COORDINATOR:").
        """
        reasons = []

        total_cost = costs.get("total_cost_usd", 0.0)
        if total_cost > self.daily_budget_limit:
            reasons.append(
                f"Daily AI budget exceeded (${total_cost:.2f} > ${self.daily_budget_limit:.2f})"
            )

        stale_count = sum(1 for v in health.values() if v not in ("OK",))
        if stale_count >= 2:
            reasons.append(f"Multiple agents inactive ({stale_count}/{len(AGENTS_TO_WATCH)} failures)")

        controls = self.repo.get_supervisor_controls()

        if reasons:
            logger.warning(f"CIRCUIT BREAKER: {'; '.join(reasons)}")
            if not controls.get("emergency_stop"):
                self.repo.update_supervisor_controls({
                    **controls,
                    "emergency_stop": 1,
                    "ai_reasoning": f"COORDINATOR: Circuit Breaker. {'; '.join(reasons)}",
                })
                self.notifier.broadcast(
                    f"CIRCUIT BREAKER TRIGGERED:\n{chr(10).join(reasons)}", level="ERROR"
                )
                logger.info("Emergency Stop attivato.")
        else:
            # [FIX-D] Auto-resume solo se fu il Coordinator stesso a settarlo
            reasoning = controls.get("ai_reasoning", "")
            if controls.get("emergency_stop") and reasoning.startswith("COORDINATOR:"):
                self.repo.update_supervisor_controls({
                    **controls,
                    "emergency_stop": 0,
                    "ai_reasoning": "COORDINATOR: All systems healthy. Auto-resuming.",
                })
                logger.info("Emergency Stop rimosso automaticamente (sistemi sani).")
                self.notifier.broadcast("CIRCUIT BREAKER RESOLVED: trading ripreso.", level="INFO")

    # ── Report Synthesis [FIX-B, FIX-E] ───────────────────────────────────

    def _get_recent_closed_trades(self, limit: int = 10) -> list:
        """
        [FIX-B] Sostituisce repo.get_history() inesistente.
        Query diretta su trade_outcomes.
        """
        try:
            with self.repo._conn() as conn:
                rows = conn.execute(
                    "SELECT asset, pnl_pct, was_profitable, closed_at "
                    "FROM trade_outcomes ORDER BY closed_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"Errore lettura trade_outcomes: {e}")
            return []

    def generate_synthesis(self, health: dict, costs: dict) -> str:
        """Usa NVIDIA LLM per generare un report markdown."""
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            return "[COORDINATOR] NVIDIA_API_KEY non trovata. Report non generato."

        model = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
        url = "https://integrate.api.nvidia.com/v1/chat/completions"

        open_trades = self.repo.get_open_decisions()
        # [FIX-E] usa query diretta invece di get_history()
        recent_closed = self._get_recent_closed_trades(limit=10)

        wins = sum(1 for t in recent_closed if t.get("was_profitable"))
        winrate = (wins / len(recent_closed) * 100) if recent_closed else 0.0
        net_pnl = sum(t.get("pnl_pct", 0.0) for t in recent_closed)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        prompt = f"""You are the Global Coordinator for TENGU V11.5 Multi-Agent Trading Bot.
Date: {today}

SYSTEM HEALTH:
{json.dumps(health, indent=2)}

API COSTS TODAY: ${costs.get('total_cost_usd', 0.0):.4f} / ${self.daily_budget_limit:.2f} budget

TRADING STATS (last 10 closed trades):
- Open positions: {len(open_trades)}
- Closed trades analyzed: {len(recent_closed)}
- Win Rate: {winrate:.1f}%
- Net PnL: {net_pnl:+.2f}%

TASK: Write a concise 2-paragraph Markdown report.
1. System health evaluation.
2. Trading performance summary.
End with: **Verdict: GREEN / YELLOW / RED**

Be specific. Use absolute date {today}. Max 300 tokens.
"""

        try:
            res = requests.post(
                url,
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3, "max_tokens": 400},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"generate_synthesis failed: {e}")
            return f"[COORDINATOR] Report generation failed: {e}"

    # ── Main Cycle [FIX-F] ───────────────────────────────────────────────────

    def run_cycle(self) -> None:
        """Ciclo principale: health check, circuit breaker, report opzionale."""
        try:
            logger.info("Coordinator cycle starting...")
            health = self.get_system_health()
            costs = self.tracker.get_summary()

            # Log health
            for agent, status in health.items():
                icon = "OK" if status == "OK" else "WARN"
                logger.info(f"  [{icon}] {agent}: {status}")

            # Circuit breaker
            self.check_circuit_breakers(health, costs)

            # Report giornaliero (throttled a 4h) [FIX-F]
            report_path = PROJECT_ROOT / "ai_memory" / "project" / "daily_synthesis.md"
            report_path.parent.mkdir(parents=True, exist_ok=True)

            should_report = True
            if report_path.exists():
                mtime = datetime.fromtimestamp(report_path.stat().st_mtime, tz=timezone.utc)
                if (datetime.now(timezone.utc) - mtime) < timedelta(hours=REPORT_MIN_INTERVAL_HOURS):
                    should_report = False
                    logger.info(f"Report gia' aggiornato nelle ultime {REPORT_MIN_INTERVAL_HOURS}h. Skip.")

            if should_report:
                logger.info("Generazione report di sintesi...")
                report_content = self.generate_synthesis(health, costs)
                try:
                    self.mm.save_typed_memory(
                        category="project",
                        name="Daily Synthesis",
                        content=report_content,
                        description="Report generato dal Coordinator Agent V11.5.",
                    )
                except Exception as e:
                    logger.warning(f"save_typed_memory fallito: {e}")

                self.notifier.broadcast(
                    f"Daily Report TENGU V11.5:\n{report_content[:1500]}"
                )
                report_path.write_text(report_content, encoding="utf-8")
                logger.info(f"Report salvato in {report_path}")

            # Heartbeat
            self.repo.update_service_heartbeat(
                "coordinator",
                json.dumps({
                    "status": "watching",
                    "health": health,
                    "cost_usd": costs.get("total_cost_usd", 0.0),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }),
            )

            logger.info("Coordinator cycle complete.")

        except Exception as e:
            logger.error(f"Coordinator error: {e}", exc_info=True)


def main() -> None:
    coordinator = Coordinator()
    logger.info("TENGU V11.5 Coordinator Agent starting...")
    # [FIX-F] schedule invece di sleep fisso
    schedule.every(5).minutes.do(coordinator.run_cycle)
    coordinator.run_cycle()  # Prima esecuzione immediata
    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    main()
