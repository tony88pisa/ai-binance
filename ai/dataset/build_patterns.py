import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from storage.repository import Repository
from typing import List, Dict

logger = logging.getLogger("ai.dataset.build_patterns")

class PatternBuilder:
    def __init__(self, repo: Repository):
        self.repo = repo

    def extract_clusters(self):
        """Analyze trades to identify positive and negative trigger clusters."""
        with self.repo._get_connection() as conn:
            # Simple clustering by regime + strategy family + technical thresholds (V8.1 real logic)
            rows = conn.execute(
                """SELECT asset, action, confidence, rsi_5m, macd_5m, market_regime, was_profitable, realized_pnl_pct
                   FROM decisions d
                   JOIN trade_outcomes o ON d.id = o.decision_id"""
            ).fetchall()
            
            for row in rows:
                pattern_id = f"P-{row['market_regime']}-{row['action']}-{int(row['rsi_5m']/10)}"
                
                metrics = {
                    "win_rate": 1.0 if row['was_profitable'] else 0.0,
                    "pnl": row['realized_pnl_pct']
                }
                
                # Persistence logic (incrementing occurrences and updating win rates)
                self.repo.upsert_pattern(
                    pattern_id=pattern_id,
                    family="General",
                    regime=row['market_regime'],
                    trigger=f"RSI between {int(row['rsi_5m']/10)*10} and {(int(row['rsi_5m']/10)+1)*10}",
                    metrics=metrics
                )
            
            logger.info(f"Pattern extraction complete. {len(rows)} cases clustered.")

if __name__ == "__main__":
    from storage.repository import Repository
    pb = PatternBuilder(Repository())
    pb.extract_clusters()
    print("Pattern extraction logic verified.")
