import time
import json
import logging
from datetime import datetime, timezone, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.repository import Repository

logging.basicConfig(level=logging.INFO, format="%(asctime)s - RECOVERY - %(levelname)s - %(message)s")
logger = logging.getLogger("self_healing")

class SelfHealingDaemon:
    def __init__(self):
        self.repo = Repository()
        
    def perform_rollback(self, conn, current_live_id, reason):
        """Disattiva il deployment corrente e torna all'ultimo stabile."""
        # Segna l'attuale come fallito/rolled_back
        conn.execute("UPDATE live_deployments SET status='rolled_back' WHERE id=?", (current_live_id,))
        
        # Cerca l'ultimo deployment rimasto `active` o `archived` che non sia `rolled_back`
        last_stable = conn.execute(
            "SELECT id, strategy_tag, model_tag FROM live_deployments "
            "WHERE status != 'rolled_back' AND id < ? ORDER BY id DESC LIMIT 1",
            (current_live_id,)
        ).fetchone()
        
        if last_stable:
            conn.execute("UPDATE live_deployments SET status='active' WHERE id=?", (last_stable["id"],))
            logger.warning(f"ROLLBACK ESEGUITO: Tornati a Strat [{last_stable['strategy_tag']}] e Model [{last_stable['model_tag']}]")
            return f"Rolled back to {last_stable['strategy_tag']} | {last_stable['model_tag']}"
        else:
            logger.error("ROLLBACK FALLITO: Nessun backup stabile trovato. Il bot richiede intervento manuale!")
            return "FATAL: No stable fallback."

    def check_and_heal(self):
        """Legge LiveGuard. Se CRITICAL, esegue rollback."""
        action_taken = "Nessuna anomalia"
        details = ""
        
        with self.repo._get_connection() as conn:
            # Check LiveGuard
            lg_row = conn.execute("SELECT config_json FROM service_state WHERE service_name='liveguard'").fetchone()
            if lg_row and lg_row["config_json"]:
                lg_data = json.loads(lg_row["config_json"])
                if lg_data.get("status") == "CRITICAL" and lg_data.get("blocked") == True:
                    logger.warning("LiveGuard CRITICAL Rilevato! Avvio protocollo di Auto-Heal (Rollback)...")
                    
                    # Cerca l'attivo
                    active_dep = conn.execute("SELECT id FROM live_deployments WHERE status='active' ORDER BY deployed_at DESC LIMIT 1").fetchone()
                    if active_dep:
                        action_taken = "ROLLBACK COMPLETATO"
                        details = self.perform_rollback(conn, active_dep["id"], lg_data.get("incidents", ["Sconosciuto"])[0])
                        
                        # Reset LiveGuard status locally to avoid infinite rollback loops
                        lg_data["status"] = "RECOVERED"
                        lg_data["blocked"] = False
                        lg_data["incidents"].append("Auto-Healed by Rollback Manager.")
                        conn.execute("UPDATE service_state SET config_json=? WHERE service_name='liveguard'", (json.dumps(lg_data),))
                        conn.commit()

            # Cleanup Vecchi Artefatti (Decisioni pending > 3gg)
            threashold = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
            deleted = conn.execute("DELETE FROM decisions WHERE status='pending' AND timestamp_utc < ?", (threashold,)).rowcount
            if deleted > 0:
                logger.info(f"Cleanup: rimosse {deleted} vecchie decisioni pending o orfane.")
                
            state = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last_action": action_taken,
                "recovery_details": details
            }
            
            conn.execute(
                "INSERT INTO service_state (service_name, status, last_heartbeat, config_json) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(service_name) DO UPDATE SET "
                "status = excluded.status, last_heartbeat = excluded.last_heartbeat, config_json = excluded.config_json",
                ("self_healing", "active", datetime.now(timezone.utc).isoformat(), json.dumps(state))
            )
            conn.commit()
            return state

    def run_cycle(self):
        logger.info("Avviato check di Self-Healing e Recovery (Module 13)...")
        self.check_and_heal()
        logger.info("Self-Healing check concluso.")

if __name__ == "__main__":
    healer = SelfHealingDaemon()
    healer.run_cycle()
