import requests
import json
import logging
import subprocess
from datetime import datetime

logger = logging.getLogger("ai.mcp_client")

class TenguMCPClient:
    """
    Bridge client che espone i tool al protocollo MCP-like compatibile con il tool-calling nativo di Ollama/Gemma 4.
    """
    def __init__(self):
        # Definisco l'array dei tool nel formato API atteso da Ollama / OpenAI
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "fetch_web_news",
                    "description": "Ottieni i titoli delle ultime notizie finanziarie per un asset specifico. Usalo se c'e' alta volatilita' o se i dati tecnici sono contraddittori.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "asset": {
                                "type": "string",
                                "description": "Il nome dell'asset (es. BTC, ETH, AAPL)"
                            }
                        },
                        "required": ["asset"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "ask_human_override",
                    "description": "Invia una notifica di emergenza WhatsApp all'umano supervisore chiedendo un'opinione prima di un trade rischioso.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "Il messaggio di allarme da inviare su WP all'utente."
                            }
                        },
                        "required": ["message"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_memories",
                    "description": "Cerca nella memoria semantica a lungo termine (Supermemory). Usalo per trovare regole storiche, vecchi trade o approfondimenti su un asset.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "La query di ricerca semantica (es. 'Bitcoin halving lessons 2024')"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "add_memory",
                    "description": "Salva una nuova tesi o un'osservazione importante nella memoria a lungo termine dello Swarm.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Il contenuto della memoria da salvare (formato testo o JSON string)"
                            }
                        },
                        "required": ["content"]
                    }
                }
            }
        ]
        
    def get_ollama_tools_schema(self):
        """Specifica JSON dei tools da iniettare in ogni chiamata LLM."""
        return self.tools
        
    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Esegue il tool chiamato dall'LLM e restituisce l'esito testuale per la memoria a breve termine."""
        logger.info(f"⚡ [MCP TOOL CALL] Esecuzione: {tool_name} con args: {arguments}")
        
        try:
            if tool_name == "fetch_web_news":
                return self._tool_fetch_web_news(arguments.get("asset", ""))
            elif tool_name == "ask_human_override":
                return self._tool_ask_human_override(arguments.get("message", ""))
            elif tool_name == "search_memories":
                return self._tool_supermemory_search(arguments.get("query", ""))
            elif tool_name == "add_memory":
                return self._tool_supermemory_add(arguments.get("content", ""))
            else:
                return f"Errore MCP: Tool {tool_name} inesistente."
        except Exception as e:
            err = f"Errore interno nell'esecuzione del tool {tool_name}: {e}"
            logger.error(err)
            return err

    def _tool_fetch_web_news(self, asset: str) -> str:
        """Simulatore o connettore reale per le news finanziarie (Integrazione Web)."""
        # Per MVP di Aprile 2026: mockiamo la fetch web o usiamo una API libera.
        # Immaginiamo di leggere da cryptopanic o un bridge rss.
        if "BTC" in asset.upper():
            return "Risultato Ricerca Web: 'La Federal Reserve annuncia tassi stabili. Binance registra flussi record in entrata su Bitcoin.'"
        elif "SOL" in asset.upper():
            return "Risultato Ricerca Web: 'Tensione sulla rete Solana, un recente bug riduce la probabilita' di breakout.'"
        return f"Risultato Ricerca Web: Nessuna news critica urgente rilevata per {asset} nelle ultime 24h."
        
    def _tool_ask_human_override(self, message: str) -> str:
        """Invia al MCP Node WhatsApp e simula la ricezione se offline."""
        logger.warning(f"💬 [WHATSAPP OUTBOUND] => {message}")
        try:
            # Integraazione REALE con il server.js WhatsApp Webhook su porta 8099
            payload = {
                "type": "custom",
                "payload": {"message": f"🤖 *Gemma 4 MCP Tool Call*\n{message}"}
            }
            resp = requests.post("http://127.0.0.1:8099", json=payload, timeout=5)
            
            if resp.status_code == 200:
                logger.info("WhatsApp inviato con successo al supervisore.")
                return "Notifica WhatsApp inviata con successo. Procedi assumendo che l'utente stia leggendo, ma aspetta conferme esterne per le manovre che richiedono esplicito input."
            else:
                return f"Errore server WhatsApp MCP: {resp.status_code}"
                
        except Exception as e:
            return f"Impossibile connettersi al server WhatsApp (forse non avviato tramite START_STACK): {e}"

    def _tool_supermemory_search(self, query: str) -> str:
        """Chiama il bridge MCP Supermemory o l'API diretta."""
        import os
        key = os.getenv("SUPERMEMORY_API_KEY", "").strip()
        if not key: return "Errore: SUPERMEMORY_API_KEY non configurata."
        
        try:
            # Preferisco usare la lib diretta se installata, o il bridge HTTP mcp-remote
            # Per ora usiamo requests verso l'endpoint mcp-remote simulato o l'API reale
            url = "https://api.supermemory.ai/v3/search"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            resp = requests.post(url, json={"q": query, "limit": 3}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            if "data" in data:
                for item in data["data"]:
                    results.append(f"- {item.get('memory', 'N/A')}")
            
            return "Risultati Supermemory:\n" + ("\n".join(results) if results else "Nessuna memoria rilevante trovata.")
        except Exception as e:
            logger.error(f"Supermemory search tool error: {e}")
            return f"Errore Supermemory: {e}"

    def _tool_supermemory_add(self, content: str) -> str:
        """Aggiunge una memoria al layer semantico."""
        import os
        key = os.getenv("SUPERMEMORY_API_KEY", "").strip()
        if not key: return "Errore: SUPERMEMORY_API_KEY non configurata."
        
        try:
            url = "https://api.supermemory.ai/v3/documents"
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            resp = requests.post(url, json={"content": content}, timeout=10)
            resp.raise_for_status()
            return "Memoria salvata correttamente nel layer semantico."
        except Exception as e:
            logger.error(f"Supermemory add tool error: {e}")
            return f"Errore salvataggio Supermemory: {e}"
