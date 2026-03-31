import time
import json
import logging
from datetime import datetime, timezone, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.repository import Repository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - LIVEGUARD - %(levelname)s - %(message)s")
logger = logging.getLogger("liveguard")

class LiveGuard:
    def __init__(self):
        self.repo = Repository()
        self.max_continuous_losses = 5
        self.max_daily_drawdown = -50.0  # Assolute USD threshold for proxy or %
        
    def check_health(self):
        """Monitora i trade live e attiva blocchi se i parametri sballano."""
        status = "OK"
        incidents = []
        consecutive_losses = 0
        blocked = False
        
        with self.repo._get_connection() as conn:
            # 1. Check Consecutive Losses from LIVE trades (or testlab if simulating)
            # In a true live setup, we filter by env='live'
            rows = conn.execute(
                "SELECT was_profitable FROM trade_outcomes ORDER BY closed_at DESC LIMIT 10"
            ).fetchall()
            
            for r in rows:
                if not r["was_profitable"]:
                    consecutive_losses += 1
                else:
                    break
                    
            if consecutive_losses >= self.max_continuous_losses:
                status = "CRITICAL"
                blocked = True
                incidents.append(f"Raggiunto limite perdite ({consecutive_losses} max).")
                
            # 2. Daily Drawdown
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            dd_row = conn.execute(
                "SELECT SUM(realized_pnl_abs) as daily_pnl FROM trade_outcomes WHERE open_at LIKE ?", 
                (f"{today}%",)
            ).fetchone()
            
            daily_pnl = dd_row["daily_pnl"] if dd_row and dd_row["daily_pnl"] else 0.0
            if daily_pnl <= self.max_daily_drawdown:
                status = "CRITICAL"
                blocked = True
                incidents.append(f"Raggiunto Max Daily Drawdown ({daily_pnl:.2f} USDC).")
                
            # Simulate Data quality / Model unreachable
            # Here we check if `bot_sessions` updated recently
            
        guard_state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "blocked": blocked,
            "incidents": incidents,
            "consecutive_losses": consecutive_losses,
            "daily_pnl": daily_pnl
        }
        
        self.save_state(guard_state)
        return guard_state
        
    def save_state(self, state):
        with self.repo._get_connection() as conn:
            conn.execute(
                "INSERT INTO service_state (service_name, status, last_heartbeat, config_json) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(service_name) DO UPDATE SET "
                "status = excluded.status, last_heartbeat = excluded.last_heartbeat, config_json = excluded.config_json",
                ("liveguard", "blocked" if state["blocked"] else "active", datetime.now(timezone.utc).isoformat(), json.dumps(state))
            )
            conn.commit()

    def run_cycle(self):
        logger.info("Controllo diagnostico LiveGuard (Module 12) in corso...")
        self.check_health()
        logger.info("Controllo concluso.")

if __name__ == "__main__":
    guard = LiveGuard()
    guard.run_cycle()
