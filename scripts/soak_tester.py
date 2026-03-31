import psutil
import time
import json
import logging
from datetime import datetime, timezone
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.repository import Repository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - SOAK_TEST - %(levelname)s - %(message)s")
logger = logging.getLogger("soak_test")

class SoakTester:
    def __init__(self):
        self.repo = Repository()
        self.start_time = datetime.now(timezone.utc)
        self.error_count = 0
        
    def measure_stability(self):
        """Misura l'uptime, memory leak e api failures per il soak test 24/7."""
        uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        # Memory usage in MB
        process = psutil.Process(os.getpid())
        mem_mb = process.memory_info().rss / (1024 * 1024)
        
        # Conta gli switch 'ROLLBACK COMPLETATO' e crash dal service_state healing
        recovery_count = 0
        blocked_trades = 0
        
        with self.repo._get_connection() as conn:
            heal_row = conn.execute("SELECT config_json FROM service_state WHERE service_name='self_healing'").fetchone()
            if heal_row and heal_row["config_json"]:
                heal_data = json.loads(heal_row["config_json"])
                if heal_data.get("last_action") == "ROLLBACK COMPLETATO":
                    recovery_count += 1
            
            # Simulated error scanning da freqtrade logs
            # In a real environment, read from `user_data/logs/freqtrade.log`
            log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_data", "logs", "freqtrade.log")
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[-500:] # Last 500
                        errors = [l for l in lines if "ERROR" in l]
                        self.error_count = len(errors)
                except Exception:
                    pass
        
        stability_score = 100 - (self.error_count * 2) - (recovery_count * 10)
        if stability_score < 0: stability_score = 0
        
        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_hours": round(uptime_seconds / 3600, 2),
            "memory_mb": round(mem_mb, 2),
            "error_count": self.error_count,
            "recovery_count": recovery_count,
            "stability_score": stability_score,
            "status": "STABLE" if stability_score >= 80 else "DEGRADED"
        }
        
        with self.repo._get_connection() as conn:
            conn.execute(
                "INSERT INTO service_state (service_name, status, last_heartbeat, config_json) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(service_name) DO UPDATE SET "
                "status = excluded.status, last_heartbeat = excluded.last_heartbeat, config_json = excluded.config_json",
                ("soak_tester", "active", datetime.now(timezone.utc).isoformat(), json.dumps(state))
            )
            conn.commit()
            
        return state

    def run_cycle(self):
        logger.info("Avviato check di Soak Testing (Stability) (Module 14)...")
        self.measure_stability()
        logger.info("Soak check concluso.")

if __name__ == "__main__":
    tester = SoakTester()
    tester.run_cycle()
