"""
TENGU V12 — GEM SCANNER (AUTO-DISCOVERY)
==========================================
Ispirato da: crypto-bd-agent (antigravity-awesome-skills)

Scansiona automaticamente l'exchange per scoprire nuove gemme (token ad alta crescita)
basandosi su:
  1. Top Gainers 24h (coins con maggior incremento)
  2. Volume Spike Detection (coins con volume anomalo)
  3. Filtri di sicurezza: min volume, min market cap, no stablecoin

Produce una lista di simboli candidati da passare a TokenScorer + SquadCrypto.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import ccxt

logger = logging.getLogger("gem_scanner")


@dataclass
class GemCandidate:
    """Un token scoperto dallo scanner come potenziale gem."""
    symbol: str
    price: float
    change_24h: float          # % variazione 24h
    volume_24h_usd: float      # Volume in USD
    discovery_reason: str      # "top_gainer" | "volume_spike" | "momentum_breakout"
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "change_24h": round(self.change_24h, 2),
            "volume_24h_usd": round(self.volume_24h_usd, 2),
            "discovery_reason": self.discovery_reason,
        }


class GemScanner:
    """
    Auto-discovery di nuove gem dall'exchange.
    
    Strategia:
      1. Fetch di tutti i ticker USDT dall'exchange
      2. Filtra per criteri di sicurezza (volume minimo, no stablecoin)
      3. Classifica per "interesse" (gainers + volume spike)
      4. Ritorna top N candidati
    """

    # Filtri di sicurezza
    MIN_VOLUME_24H_USD = 100_000      # Min $100K volume 24h
    MIN_PRICE_USD = 0.0000001         # No prezzo zero
    MAX_CANDIDATES = 10               # Max candidati per ciclo
    
    # Stablecoin e token da escludere
    EXCLUDED_BASES = {
        "USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDP",
        "USDD", "PYUSD", "UST", "EUR", "GBP", "BRL", "TRY",
        "AEUR", "BFUSD", "LDUSDT",
    }
    
    # Token rischiosi / delisted noti
    EXCLUDED_SYMBOLS = set()
    
    def __init__(self, exchange: ccxt.Exchange, existing_symbols: list[str] = None):
        """
        Args:
            exchange: Istanza ccxt dell'exchange
            existing_symbols: Simboli già monitorati (per evitare duplicati)
        """
        self.exchange = exchange
        self.existing_symbols = set(existing_symbols or [])
    
    def scan(self, strategy: str = "all") -> list[GemCandidate]:
        """
        Esegue la scansione completa.
        
        Args:
            strategy: "gainers" | "volume_spike" | "all"
            
        Returns:
            Lista di GemCandidate ordinati per interesse (migliori prima)
        """
        logger.info("[GEM_SCANNER] Inizio scansione gem...")
        
        try:
            tickers = self.exchange.fetch_tickers()
        except Exception as e:
            logger.error(f"[GEM_SCANNER] Errore fetch tickers: {e}")
            return []
        
        # Filtro base: solo USDT pairs, esclude stablecoin
        usdt_tickers = {}
        for symbol, ticker in tickers.items():
            if not symbol.endswith("/USDT"):
                continue
            base = symbol.split("/")[0]
            if base in self.EXCLUDED_BASES:
                continue
            if symbol in self.EXCLUDED_SYMBOLS:
                continue
            # Filtro volume minimo
            vol = ticker.get("quoteVolume") or 0
            if vol < self.MIN_VOLUME_24H_USD:
                continue
            # Filtro prezzo
            price = ticker.get("last") or 0
            if price < self.MIN_PRICE_USD:
                continue
            usdt_tickers[symbol] = ticker
        
        logger.info(f"[GEM_SCANNER] {len(usdt_tickers)} pairs valide trovate (filtrate da {len(tickers)} totali)")
        
        candidates = []
        
        if strategy in ("gainers", "all"):
            candidates.extend(self._find_gainers(usdt_tickers))
        
        if strategy in ("volume_spike", "all"):
            candidates.extend(self._find_volume_spikes(usdt_tickers))
        
        # Deduplicazione e ordinamento
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c.symbol not in seen and c.symbol not in self.existing_symbols:
                seen.add(c.symbol)
                unique_candidates.append(c)
        
        # Ordina per volume (proxy di sicurezza/liquidità)
        unique_candidates.sort(key=lambda c: c.volume_24h_usd, reverse=True)
        result = unique_candidates[:self.MAX_CANDIDATES]
        
        for c in result:
            logger.info(
                f"[GEM_SCANNER] GEM TROVATA: {c.symbol} | "
                f"Change: {c.change_24h:+.1f}% | Vol: ${c.volume_24h_usd/1e6:.2f}M | "
                f"Reason: {c.discovery_reason}"
            )
        
        return result
    
    def _find_gainers(self, tickers: dict) -> list[GemCandidate]:
        """Trova i top gainers 24h (esclude pump estremi > 100%)."""
        candidates = []
        
        for symbol, ticker in tickers.items():
            change = ticker.get("percentage") or 0
            
            # Sweet-spot: +5% a +60% (evita pump & dump da +100%)
            if 5.0 <= change <= 60.0:
                candidates.append(GemCandidate(
                    symbol=symbol,
                    price=float(ticker.get("last", 0)),
                    change_24h=float(change),
                    volume_24h_usd=float(ticker.get("quoteVolume", 0)),
                    discovery_reason="top_gainer",
                ))
        
        # Top 5 per percentuale
        candidates.sort(key=lambda c: c.change_24h, reverse=True)
        return candidates[:5]
    
    def _find_volume_spikes(self, tickers: dict) -> list[GemCandidate]:
        """
        Trova token con volume anomalo.
        Un token con volume 24h > 3x la sua media "tipica" è interessante.
        (Qui usiamo il rapporto volume/market-cap come proxy.)
        """
        candidates = []
        
        for symbol, ticker in tickers.items():
            vol = float(ticker.get("quoteVolume", 0))
            price = float(ticker.get("last", 0))
            change = float(ticker.get("percentage", 0))
            
            if price <= 0:
                continue
            
            # Volume/Price ratio come proxy di "eccitazione"
            # Un ratio molto alto indica che il token sta muovendo molto volume
            # rispetto al suo prezzo — segno di forte interesse
            vol_ratio = vol / (price * 1e6) if price > 0 else 0
            
            # Soglia: volume > $500K e ratio alto e cambio positivo ma non pump
            if vol > 500_000 and vol_ratio > 50 and 0 < change < 80:
                candidates.append(GemCandidate(
                    symbol=symbol,
                    price=price,
                    change_24h=change,
                    volume_24h_usd=vol,
                    discovery_reason="volume_spike",
                ))
        
        candidates.sort(key=lambda c: c.volume_24h_usd, reverse=True)
        return candidates[:5]
    
    def update_existing_symbols(self, symbols: list[str]) -> None:
        """Aggiorna la lista dei simboli già monitorati."""
        self.existing_symbols = set(symbols)
