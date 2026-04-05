import os
import requests
import logging

logger = logging.getLogger("modules.notifications_hub")

class NotificationsHub:
    """
    Gestore di Notifiche Multicanale (Ispirato a daily_stock).
    Utilizza webhook standard (gratuiti) su Discord o Telegram
    per inviare i log cruciali, i trade e gli avvisi di emergenza del Coordinator.
    """
    def __init__(self):
        # Carica le webhook e configuration keys da env se disponibili
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        # Di default, attiva i canali solo se le env var sono configurate
        self.use_discord = bool(self.discord_webhook)
        self.use_telegram = bool(self.telegram_bot_token and self.telegram_chat_id)

    def broadcast(self, message: str, level: str = "INFO"):
        """Invia un messaggio testuale a tutti i canali attivi"""
        prefix = "🚨 [EMERGENCY]" if level == "ERROR" else "📊 [TENGU V10]"
        full_msg = f"{prefix}\n{message}"
        
        success = False
        if self.use_discord:
            success |= self._send_discord(full_msg)
        if self.use_telegram:
            success |= self._send_telegram(full_msg)
            
        if not (self.use_discord or self.use_telegram):
            # Se nessun canale è configurato, loggiamo solo (fallback)
            logger.info(f"NotificationsHub (No Webhooks Configured): {full_msg}")
        return success

    def _send_discord(self, message: str) -> bool:
        try:
            payload = {"content": message, "username": "Tengu V10 - Coordinator"}
            res = requests.post(self.discord_webhook, json=payload, timeout=5)
            return res.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Errore invio Discord: {e}")
            return False

    def _send_telegram(self, message: str) -> bool:
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {"chat_id": self.telegram_chat_id, "text": message}
            res = requests.post(url, json=payload, timeout=5)
            return res.status_code == 200
        except Exception as e:
            logger.error(f"Errore invio Telegram: {e}")
            return False
