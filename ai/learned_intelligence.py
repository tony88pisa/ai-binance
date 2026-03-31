import json
import logging
from datetime import datetime, timezone
from storage.repository import Repository
from typing import List, Dict

logger = logging.getLogger("ai.learned_intelligence")

class LearnedIntelligence:
    def __init__(self, repo: Repository):
        self.repo = repo

    def summarize_today(self) -> Dict:
        """REAL V8.1.1 summarized insights from SQLite database."""
        with self.repo._get_connection() as conn:
            # 1. Fetch performance by Market Regime (REAL SQL)
            regime_stats = conn.execute(
                """SELECT market_regime, 
                          COUNT(*) as total_trades, 
                          AVG(realized_pnl_pct) as avg_pnl, 
                          AVG(CAST(was_profitable AS FLOAT)) as win_rate
                   FROM decisions d
                   JOIN trade_outcomes o ON d.id = o.decision_id
                   WHERE o.closed_at >= date('now', 'start of day')
                   GROUP BY market_regime
                   ORDER BY avg_pnl DESC"""
            ).fetchall()
            
            # 2. Fetch changes applied in the last 24h
            recent_changes = conn.execute(
                """SELECT change_summary 
                   FROM learned_changes 
                   WHERE created_at >= date('now', '-1 day') 
                   LIMIT 1"""
            ).fetchone()

            summary = "No trading activity recorded for the current tracking period."
            if regime_stats:
                top = dict(regime_stats[0])
                summary = (f"Confirmed high efficiency in {top['market_regime']} regime "
                           f"with {top['win_rate']*100:.1f}% win rate. ")
                if recent_changes:
                    summary += f"Recent optimization: {recent_changes['change_summary']}"
            
            return {
                "summary": summary,
                "regime_stats": [dict(r) for r in regime_stats],
                "last_update": datetime.now(timezone.utc).isoformat()
            }

    def list_learned_changes(self) -> List[Dict]:
        """Fetch real history of strategy evolutions."""
        with self.repo._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM learned_changes ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            return [dict(r) for r in rows]

if __name__ == "__main__":
    from storage.repository import Repository
    li = LearnedIntelligence(Repository())
    print(f"V8.1.1 Intelligence: {li.summarize_today()['summary']}")
