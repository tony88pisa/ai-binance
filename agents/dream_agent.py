"""
TENGU V11.5 — DREAM AGENT (FIXED)
====================================
Fix applicati:
  [FIX-2] Campo pnl_pct unificato (era realized_pnl_pct — KeyError corretto).
  [FIX-4] Try/except attorno a NvidiaTeacher import (startup safe).
  [FIX-5] Gestione graceful se outcomes vuoti.
"""
import time
import json
import logging
import os
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path
import schedule
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from config.settings import get_settings
from storage.repository import Repository
from storage.memory_manager import MemoryManager
from telemetry.cost_tracker import get_cost_tracker
from storage.superbrain import get_superbrain

settings = get_settings()

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DREAM] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "dream_agent.log", encoding="utf-8", delay=True),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("dream_agent")

# [FIX-4] Import NvidiaTeacher con fallback esplicito
try:
    from ai.nvidia_teacher import NvidiaTeacher
    _NVIDIA_AVAILABLE = True
    logger.info("NvidiaTeacher disponibile.")
except ImportError as e:
    _NVIDIA_AVAILABLE = False
    logger.warning(f"NvidiaTeacher non importabile: {e}. Dream Consolidation usera' fallback locale.")


class DreamAgent:
    """
    Memory Consolidation Agent (Auto-Dream V11.5).
    4 Fasi:
      1. ORIENT  — Stato corrente del sistema.
      2. GATHER  — Estrazione segnali (Win Rate per asset).
      3. CONSOLIDATE — Sintesi nuove Golden Rules via LLM.
      4. PRUNE   — Auto-purge regole low-performance + compaction.
    """

    WIN_RATE_THRESHOLD = 45.0
    MIN_TRADES_FOR_PRUNE = 2

    def __init__(self):
        self.repo = Repository()
        self.mm = MemoryManager(str(PROJECT_ROOT))
        self.tracker = get_cost_tracker(str(PROJECT_ROOT))

    # ── Phase 1 Helper ───────────────────────────────────────────────

    def _get_recent_performance(self) -> dict:
        """
        Fetcha outcome delle ultime 24 ore.
        [FIX-2] Usa 'pnl_pct' (campo standard unificato con squad_crypto).
        """
        try:
            outcomes = self.repo.get_recent_outcomes(days=1)
        except Exception as e:
            logger.error(f"Errore lettura outcomes: {e}")
            outcomes = []

        # [FIX-5] Guard outcomes vuoti
        if not outcomes:
            return {"total_trades": 0, "wins": 0, "losses": 0, "net_pnl_pct": 0.0}

        win_count = sum(1 for o in outcomes if o.get("was_profitable", False))
        loss_count = len(outcomes) - win_count
        # [FIX-2] 'pnl_pct' — era 'realized_pnl_pct' che causava KeyError
        net_pnl = sum(o.get("pnl_pct", 0.0) for o in outcomes)

        return {
            "total_trades": len(outcomes),
            "wins": win_count,
            "losses": loss_count,
            "net_pnl_pct": round(net_pnl, 4),
        }

    # ── Phase 2 Helper ───────────────────────────────────────────────

    def _compute_asset_report(self, outcomes: list) -> tuple:
        """
        Costruisce il report per asset e identifica quelli low-performance.
        Ritorna (asset_report_str, low_perf_assets_list).
        """
        if not outcomes:
            return "Nessun trade negli ultimi 3 giorni.", []

        assets = set(o.get("asset", "UNKNOWN") for o in outcomes)
        report_lines = []
        low_perf = []

        for asset in sorted(assets):
            asset_outcomes = [o for o in outcomes if o.get("asset") == asset]
            wins = sum(1 for o in asset_outcomes if o.get("was_profitable", False))
            total = len(asset_outcomes)
            wr = (wins / total * 100) if total > 0 else 0.0
            # [FIX-2] usa pnl_pct (campo unificato)
            avg_pnl = sum(o.get("pnl_pct", 0.0) for o in asset_outcomes) / total if total > 0 else 0.0
            report_lines.append(f"  - {asset}: WR={wr:.0f}% | {total} trade | avg PnL={avg_pnl:+.2f}%")

            if total >= self.MIN_TRADES_FOR_PRUNE and wr < self.WIN_RATE_THRESHOLD:
                low_perf.append(asset)

        return "\n".join(report_lines), low_perf

    # ── LLM Consolidation (with fallback) ────────────────────────────

    def _consolidate_via_llm(self, prompt: str) -> str | None:
        """Chiama NvidiaTeacher se disponibile, altrimenti None."""
        if not _NVIDIA_AVAILABLE:
            logger.warning("NvidiaTeacher non disponibile — skip consolidation LLM.")
            return None
        try:
            teacher = NvidiaTeacher(self.repo)
            result = teacher.ask(prompt)
            return result
        except Exception as e:
            logger.error(f"NvidiaTeacher call failed: {e}")
            return None

    # ── Main Dream Cycle ───────────────────────────────────────────────

    def run_dream_cycle(self) -> None:
        logger.info("Auto-Dream 4-Phase V11.5")
        brain = get_superbrain()

        # ── PHASE 1: ORIENT ──────────────────────────────────────────────
        logger.info("[1/4] ORIENT — Stato corrente sistema...")
        perf = self._get_recent_performance()
        existing_strategy = brain.get_current_strategy()
        logger.info(
            f"  Performance 24h: {perf['total_trades']} trade | "
            f"{perf['wins']}W/{perf['losses']}L | PnL netto: {perf['net_pnl_pct']:+.2f}%"
        )

        # ── PHASE 2: GATHER ──────────────────────────────────────────────
        logger.info("[2/4] GATHER — Estrazione segnali di performance...")
        try:
            outcomes_3d = self.repo.get_outcomes_with_details(days=3)
        except Exception as e:
            logger.error(f"Errore get_outcomes_with_details: {e}")
            outcomes_3d = []

        feedback = brain.get_recent_feedback() or "Nessun feedback recente."
        asset_report, low_perf_assets = self._compute_asset_report(outcomes_3d)

        if low_perf_assets:
            logger.warning(f"Asset low-performance identificati: {low_perf_assets}")

        # ── PHASE 3: CONSOLIDATE ─────────────────────────────────────────
        logger.info("[3/4] CONSOLIDATE — Sintesi nuove Golden Rules...")

        today_abs = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        prompt = f"""You are the TENGU V11.5 DREAM AGENT. Synthesis mode.
Current Date: {today_abs}
Recent PnL (24h): {perf["net_pnl_pct"]:+.2f}% ({perf["wins"]}W / {perf["losses"]}L)

ASSET PERFORMANCE (Last 3 Days):
{asset_report}

RECENT FEEDBACK FROM SUPERBRAIN:
{feedback}

EXISTING STRATEGY:
{existing_strategy or "No strategy stored yet."}

TASK:
1. Write a TACTICAL STRATEGY for the next 2 hours (max 3 sentences).
2. Generate exactly 3 GOLDEN RULES in format: [RULE] | [WHY] | [HOW]
3. List assets to BLACKLIST (WR < 45%, min 2 trades). If none, write "NONE".

RULES:
- NEVER use relative dates. Always use absolute date {today_abs}.
- Be concise. Max 200 tokens total.
"""

        new_strategy = self._consolidate_via_llm(prompt)
        if new_strategy:
            brain.remember_strategy(new_strategy)
            logger.info("Nuova strategia consolidata nel SuperBrain.")
        else:
            logger.info("Nessuna nuova strategia (LLM non disponibile o errore).")

        # ── PHASE 4: PRUNE & INDEX ─────────────────────────────────────────
        logger.info("[4/4] PRUNE — Pulizia SuperBrain...")

        for asset in low_perf_assets:
            try:
                brain.demote_rules_for_asset(asset)
                logger.info(f"  Regole per {asset} retrocesse (WR < {self.WIN_RATE_THRESHOLD}%).")
            except Exception as e:
                logger.warning(f"  demote_rules_for_asset({asset}) fallito: {e}")

        try:
            brain.compact_index(max_lines=20)
            logger.info("  Index compacted (max 20 regole).")
        except Exception as e:
            logger.warning(f"  compact_index fallito: {e}")

        self.repo.update_service_heartbeat("dream_agent", json.dumps({
            "status": "completed",
            "last_dream": today_abs,
            "trades_analyzed": len(outcomes_3d),
            "low_perf_assets": low_perf_assets,
            "llm_available": _NVIDIA_AVAILABLE,
        }))

        logger.info("Dream Cycle Complete")


def main() -> None:
    agent = DreamAgent()
    agent.run_dream_cycle()
    schedule.every(2).hours.do(agent.run_dream_cycle)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
