"""
MCP Client V2 — Model Context Protocol Emulator.
Ispirato da prism-insight. Fornisce strumenti gratuiti al Decision Engine
senza API a pagamento, usando endpoint pubblici (CoinGecko, Alternative.me, RSS).
"""
import requests
import logging
import json
from datetime import datetime

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

logger = logging.getLogger("ai.mcp_client")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


class MCPClient:
    """Lightweight macro regime detector (used by Risk Controller)."""
    
    def __init__(self):
        self.headers = HEADERS

    def fetch_macro_regime(self) -> dict:
        try:
            res = requests.get("https://api.alternative.me/fng/", headers=self.headers, timeout=5)
            fng_data = res.json()
            if "data" in fng_data and len(fng_data["data"]) > 0:
                fng_value = int(fng_data["data"][0]["value"])
                fng_class = fng_data["data"][0]["value_classification"]
            else:
                fng_value = 50
                fng_class = "Neutral"

            regime = "RISK-ON" if fng_value > 55 else "RISK-OFF" if fng_value < 40 else "NEUTRAL"
            
            return {
                "mcp_source": "crypto_fng",
                "macro_regime": regime,
                "score": fng_value,
                "classification": fng_class,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"MCP Client error fetching macro: {e}")
            return {"macro_regime": "NEUTRAL", "score": 50, "error": str(e)}


class TenguMCPClient:
    """
    Full MCP Client per il Decision Engine.
    Fornisce "tools" locali che Ollama può chiamare durante la valutazione
    per arricchire il contesto prima di decidere BUY/HOLD.
    Tutti gli endpoint sono GRATUITI.
    """
    
    def __init__(self):
        self.headers = HEADERS
        self._cache = {}
        self._cache_ts = {}
    
    def _is_fresh(self, key: str, max_age_sec: int = 120) -> bool:
        if key not in self._cache_ts:
            return False
        return (datetime.now() - self._cache_ts[key]).total_seconds() < max_age_sec

    # =========================================
    # TOOL 1: Trending coins from CoinGecko
    # =========================================
    def get_trending_coins(self) -> str:
        key = "trending"
        if self._is_fresh(key):
            return self._cache[key]
        try:
            res = requests.get("https://api.coingecko.com/api/v3/search/trending", 
                             headers=self.headers, timeout=5)
            data = res.json()
            coins = data.get("coins", [])[:7]
            lines = [f"#{i+1} {c['item']['name']} ({c['item']['symbol']}) — Rank #{c['item']['market_cap_rank'] or '?'}" 
                     for i, c in enumerate(coins)]
            result = "TRENDING COINS (CoinGecko):\n" + "\n".join(lines)
            self._cache[key] = result
            self._cache_ts[key] = datetime.now()
            return result
        except Exception as e:
            return f"Trending unavailable: {e}"

    # =========================================
    # TOOL 2: Global market macro snapshot
    # =========================================
    def get_global_market_data(self) -> str:
        key = "global"
        if self._is_fresh(key):
            return self._cache[key]
        try:
            res = requests.get("https://api.coingecko.com/api/v3/global",
                             headers=self.headers, timeout=5)
            data = res.json().get("data", {})
            btc_dom = data.get("market_cap_percentage", {}).get("btc", 0)
            total_mc = data.get("total_market_cap", {}).get("usd", 0)
            total_vol = data.get("total_volume", {}).get("usd", 0)
            mc_change = data.get("market_cap_change_percentage_24h_usd", 0)
            result = (f"GLOBAL CRYPTO MARKET:\n"
                     f"Total Market Cap: ${total_mc/1e9:.1f}B (24h change: {mc_change:+.2f}%)\n"
                     f"Total Volume 24h: ${total_vol/1e9:.1f}B\n"
                     f"BTC Dominance: {btc_dom:.1f}%")
            self._cache[key] = result
            self._cache_ts[key] = datetime.now()
            return result
        except Exception as e:
            return f"Global data unavailable: {e}"

    # =========================================
    # TOOL 3: Fear & Greed Index
    # =========================================
    def get_fear_greed(self) -> str:
        key = "fng"
        if self._is_fresh(key):
            return self._cache[key]
        try:
            res = requests.get("https://api.alternative.me/fng/?limit=3", 
                             headers=self.headers, timeout=5)
            data = res.json().get("data", [])
            lines = []
            for d in data:
                lines.append(f"  {d.get('value', '?')}/100 ({d.get('value_classification', '?')}) — {d.get('timestamp', '?')}")
            result = "FEAR & GREED INDEX (last 3 days):\n" + "\n".join(lines)
            self._cache[key] = result
            self._cache_ts[key] = datetime.now()
            return result
        except Exception as e:
            return f"F&G unavailable: {e}"

    def search_web(self, query: str) -> str:
        """Esegue una ricerca web live usando DuckDuckGo e condensa i risultati."""
        if not DDGS:
            return "Web search non disponibile (duckduckgo-search non installato)."
        try:
            results = DDGS().text(query, max_results=3)
            if not results:
                return "Nessun risultato trovato."
            
            lines = [f"WEB SEARCH: '{query}'"]
            for r in results:
                lines.append(f"- {r.get('title', '')}: {r.get('body', '')}")
            return "\n".join(lines)
        except Exception as e:
            return f"Errore ricerca web: {str(e)}"

    # =========================================
    # TOOL EXECUTOR (called by decision_engine)
    # =========================================
    def execute_tool(self, tool_name: str, args: dict) -> str:
        """Execute a tool by name and return string result."""
        dispatch = {
            "get_trending_coins": lambda _: self.get_trending_coins(),
            "get_global_market_data": lambda _: self.get_global_market_data(),
            "get_fear_greed": lambda _: self.get_fear_greed(),
            "search_web": lambda args: self.search_web(args.get("query", "")),
        }
        fn = dispatch.get(tool_name)
        if fn:
            try:
                return fn(args)
            except Exception as e:
                return f"Tool error ({tool_name}): {e}"
        return f"Unknown tool: {tool_name}"

    # =========================================
    # OLLAMA TOOLS SCHEMA (JSON Schema format)
    # =========================================
    def get_ollama_tools_schema(self) -> list:
        """Return the tools schema for Ollama function calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_trending_coins",
                    "description": "Get the top 7 trending cryptocurrencies on CoinGecko right now",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_global_market_data",
                    "description": "Get global crypto market cap, volume, and BTC dominance",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_fear_greed",
                    "description": "Get the Crypto Fear and Greed Index for the last 3 days",
                    "parameters": {"type": "object", "properties": {}, "required": []}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the live web for recent crypto news, specific coin updates, or general queries using DuckDuckGo",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The exact search query to look up on the web"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
        ]
