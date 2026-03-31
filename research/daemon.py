"""
Research Daemon — always-on market intelligence service.

Runs on a configurable schedule (default: every 3 minutes).
Fetches news, normalizes, deduplicates, builds snapshots, writes state.
Completely independent from Freqtrade's candle cycle.

Usage:
  - Standalone:  python -m research.daemon
  - As thread:   from research.daemon import start_daemon_thread
"""
from __future__ import annotations

import logging
import sys
import os
import threading
import time
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.ingester import fetch_fear_and_greed, fetch_raw_news, normalize_news
from research.state_builder import build_asset_snapshots, build_macro_risk
from research.store import write_state
from research.types import ResearchState

logger = logging.getLogger("research.daemon")

CYCLE_INTERVAL_SECONDS = 180  # 3 minutes
MAX_NEWS_ITEMS = 100          # Max items in memory


class ResearchDaemon:
    """Continuous research worker."""

    def __init__(self, interval: int = CYCLE_INTERVAL_SECONDS):
        self.interval = interval
        self.seen_hashes: set[str] = set()
        self.all_news_items: list = []
        self.cycle_count = 0
        self._stop_event = threading.Event()

    def run_once(self) -> bool:
        """Execute one research cycle. Returns True on success."""
        self.cycle_count += 1
        cycle_start = time.monotonic()

        try:
            logger.info(f"📡 Research cycle #{self.cycle_count} starting...")

            # 1. Fetch raw news
            raw_items = fetch_raw_news()
            logger.debug(f"  Fetched {len(raw_items)} raw items")

            # 2. Normalize, deduplicate, score
            new_items = normalize_news(raw_items, self.seen_hashes)
            logger.debug(f"  {len(new_items)} new items after dedup")

            # 3. Add to running collection
            self.all_news_items.extend(new_items)

            # 4. Prune expired items
            before = len(self.all_news_items)
            self.all_news_items = [it for it in self.all_news_items if not it.is_expired()]
            pruned = before - len(self.all_news_items)

            # 5. Cap collection size
            if len(self.all_news_items) > MAX_NEWS_ITEMS:
                self.all_news_items = self.all_news_items[-MAX_NEWS_ITEMS:]

            # 6. Prune old hashes (keep in sync)
            active_hashes = {it.dedupe_hash for it in self.all_news_items}
            self.seen_hashes = self.seen_hashes & active_hashes

            # 7. Fetch Fear & Greed
            regime = fetch_fear_and_greed()

            # 8. Build per-asset snapshots
            asset_snapshots = build_asset_snapshots(self.all_news_items)

            # 9. Build macro risk
            macro_risk = build_macro_risk(asset_snapshots, regime)

            # 10. Write state atomically
            state = ResearchState(
                cycle_count=self.cycle_count,
                news_items=[it.to_dict() for it in self.all_news_items[-20:]],  # Keep last 20 in state
                asset_snapshots={k: v.to_dict() for k, v in asset_snapshots.items()},
                market_regime=regime.to_dict(),
                macro_risk=macro_risk.to_dict(),
            )
            success = write_state(state)

            elapsed = time.monotonic() - cycle_start
            logger.info(
                f"✅ Research cycle #{self.cycle_count} done in {elapsed:.1f}s: "
                f"{len(new_items)} new, {pruned} pruned, {len(self.all_news_items)} total, "
                f"regime={regime.regime.value}, risk={macro_risk.risk_level:.2f}"
            )
            return success

        except Exception as e:
            logger.error(f"❌ Research cycle #{self.cycle_count} failed: {e}", exc_info=True)
            return False

    def run_forever(self) -> None:
        """Run research cycles indefinitely."""
        logger.info(f"🚀 Research daemon started (interval={self.interval}s)")
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(self.interval)
        logger.info("🔴 Research daemon stopped")

    def stop(self) -> None:
        """Signal the daemon to stop."""
        self._stop_event.set()


def start_daemon_thread(interval: int = CYCLE_INTERVAL_SECONDS) -> tuple[ResearchDaemon, threading.Thread]:
    """Start the research daemon in a background thread. Returns (daemon, thread)."""
    daemon = ResearchDaemon(interval=interval)
    thread = threading.Thread(target=daemon.run_forever, name="research-daemon", daemon=True)
    thread.start()
    logger.info(f"Research daemon thread started (PID={os.getpid()}, interval={interval}s)")
    return daemon, thread


if __name__ == "__main__":
    # Standalone mode
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    daemon = ResearchDaemon()
    try:
        daemon.run_forever()
    except KeyboardInterrupt:
        daemon.stop()
        print("\nDaemon stopped by user.")
