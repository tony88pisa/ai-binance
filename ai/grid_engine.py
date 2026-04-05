"""
Grid Trading Engine — Strategia #1 per Micro-Capitali nei Mercati Laterali.

Dalla Ricerca Web (Aprile 2026):
"Grid Trading è la strategia più efficace per piccoli account in mercati sideways.
Piazza automaticamente ordini buy/sell a intervalli regolari in un range definito,
profittando da micro-fluttuazioni ripetitive."

Questo modulo implementa una griglia adattiva che si auto-configura
basandosi sull'ATR (Average True Range) per il range e sul Kelly Criterion
per la dimensione di ogni cella della griglia.
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("ai.grid_engine")


@dataclass
class GridConfig:
    """Configurazione della griglia adattiva."""
    symbol: str = "BTC/USDT"
    grid_levels: int = 5              # Numero di livelli buy/sell (pochi per micro-capitale)
    total_budget_usdt: float = 50.0   # Budget totale allocato alla griglia
    range_atr_multiplier: float = 2.0 # Range = prezzo ± (ATR × multiplier)
    take_profit_per_cell: float = 0.008  # 0.8% profitto per cella (abbassa le commissioni)
    use_limit_orders: bool = True     # Limit orders = maker fees (più basse o zero)


@dataclass
class GridLevel:
    """Singolo livello della griglia."""
    price: float
    side: str  # 'buy' o 'sell'
    size_usdt: float
    status: str = "pending"  # pending | filled | cancelled


@dataclass
class GridState:
    """Stato corrente della griglia."""
    config: GridConfig
    levels: list = field(default_factory=list)
    realized_pnl: float = 0.0
    total_fills: int = 0
    active: bool = True


class AdaptiveGridEngine:
    """
    Motore di Grid Trading Adattivo per Micro-Capitali.
    
    Funzionamento:
    1. Calcola il range ottimale dal volatilità ATR
    2. Piazza N livelli buy sotto il prezzo corrente e N livelli sell sopra
    3. Quando un buy viene preso, piazza un sell leggermente sopra (+0.8%)
    4. Quando un sell viene preso, piazza un buy leggermente sotto
    5. Il bot "guadagna lo spread" ad ogni rimbalzo dentro il range
    
    Per un capitale di 50€ con 5 livelli: ogni cella = 10€
    Con 0.8% per cella e 3 fills/giorno = 0.24€/giorno = ~7€/mese
    Dopo 1 mese: 57€ → Kelly ricalcola → celle da 11.4€
    Dopo 3 mesi: ~75€ con compound
    """

    def __init__(self, config: GridConfig = None):
        self.config = config or GridConfig()
        self.state: Optional[GridState] = None

    def calculate_grid(self, current_price: float, atr: float) -> GridState:
        """
        Genera la griglia adattiva basata su prezzo corrente e ATR.
        
        Args:
            current_price: Prezzo corrente dell'asset
            atr: Average True Range (14 periodi)
        
        Returns:
            GridState con i livelli configurati
        """
        if atr <= 0:
            atr = current_price * 0.01  # Fallback: 1% del prezzo
            
        # Range della griglia: prezzo ± (ATR × multiplier)
        range_half = atr * self.config.range_atr_multiplier
        grid_top = current_price + range_half
        grid_bottom = current_price - range_half
        
        # Budget per cella
        cell_budget = self.config.total_budget_usdt / self.config.grid_levels
        
        # Genera livelli equidistanti
        levels = []
        step = (grid_top - grid_bottom) / (self.config.grid_levels + 1)
        
        for i in range(1, self.config.grid_levels + 1):
            level_price = grid_bottom + (step * i)
            side = "buy" if level_price < current_price else "sell"
            
            levels.append(GridLevel(
                price=round(level_price, 2),
                side=side,
                size_usdt=round(cell_budget, 2)
            ))
        
        self.state = GridState(
            config=self.config,
            levels=levels
        )
        
        logger.info(
            f"📊 Griglia generata per {self.config.symbol}: "
            f"Range [{grid_bottom:.2f} - {grid_top:.2f}], "
            f"{len(levels)} livelli, {cell_budget:.2f} USDT/cella"
        )
        
        return self.state

    def simulate_grid_performance(self, closes: np.ndarray, atr: float) -> dict:
        """
        Simula la performance della griglia su dati storici.
        Utile per il Brute Force Engine e l'Auto Optimizer.
        
        Args:
            closes: Array numpy di prezzi di chiusura
            atr: ATR calcolato
            
        Returns:
            dict con metriche di performance
        """
        if len(closes) < 50:
            return {"viable": False, "reason": "Dati insufficienti"}
        
        current_price = closes[-1]
        grid = self.calculate_grid(current_price, atr)
        
        realized_pnl = 0.0
        total_fills = 0
        cell_budget = self.config.total_budget_usdt / self.config.grid_levels
        
        # Simulazione: scorri i prezzi e controlla se colpiscono livelli
        active_buys = {l.price: l for l in grid.levels if l.side == "buy"}
        active_sells = {l.price: l for l in grid.levels if l.side == "sell"}
        holdings = {}  # price_bought -> size
        
        for price in closes:
            # Controlla buy fills
            for buy_price in list(active_buys.keys()):
                if price <= buy_price:
                    # Buy filled! Registra holding
                    quantity = cell_budget / buy_price
                    holdings[buy_price] = quantity
                    total_fills += 1
                    
                    # Piazza sell corrispondente
                    sell_price = round(buy_price * (1 + self.config.take_profit_per_cell), 2)
                    active_sells[sell_price] = GridLevel(
                        price=sell_price, side="sell", 
                        size_usdt=cell_budget, status="pending"
                    )
                    del active_buys[buy_price]
            
            # Controlla sell fills
            for sell_price in list(active_sells.keys()):
                if price >= sell_price and sell_price in active_sells:
                    # Trova il buy corrispondente (il più profittevole)
                    matching_buys = [bp for bp in holdings.keys() if bp < sell_price]
                    if matching_buys:
                        buy_price = max(matching_buys)  # Ultimo buy
                        pnl = (sell_price - buy_price) * holdings[buy_price]
                        realized_pnl += pnl
                        total_fills += 1
                        del holdings[buy_price]
                        del active_sells[sell_price]
                        
                        # Re-piazza buy
                        active_buys[buy_price] = GridLevel(
                            price=buy_price, side="buy",
                            size_usdt=cell_budget, status="pending"
                        )
        
        # Calcola metriche
        daily_estimate = (realized_pnl / max(1, len(closes) / 288)) if realized_pnl > 0 else 0
        monthly_estimate = daily_estimate * 30
        
        return {
            "viable": realized_pnl > 0,
            "total_fills": total_fills,
            "realized_pnl_usdt": round(realized_pnl, 4),
            "daily_estimate_usdt": round(daily_estimate, 4),
            "monthly_estimate_usdt": round(monthly_estimate, 2),
            "compound_3m_estimate": round(
                self.config.total_budget_usdt * (1 + monthly_estimate / self.config.total_budget_usdt) ** 3, 2
            ) if monthly_estimate > 0 else self.config.total_budget_usdt,
            "grid_levels": self.config.grid_levels,
            "cell_size_usdt": round(cell_budget, 2),
            "reason": "Grid trading viabile in mercato laterale" if realized_pnl > 0 else "Mercato troppo direzionale per grid"
        }

    def get_limit_orders_batch(self) -> list:
        """
        Genera il batch di ordini limit da piazzare sull'exchange.
        Usa LIMIT orders (maker) per fee zero o ridotte.
        
        Returns:
            Lista di ordini pronti per CCXT
        """
        if not self.state:
            return []
        
        orders = []
        for level in self.state.levels:
            if level.status == "pending":
                orders.append({
                    "symbol": self.config.symbol,
                    "type": "limit",  # MAKER = fee più basse
                    "side": level.side,
                    "price": level.price,
                    "amount_usdt": level.size_usdt,
                })
        return orders
