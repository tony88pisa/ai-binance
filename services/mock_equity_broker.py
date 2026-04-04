import sqlite3
from pathlib import Path
from datetime import datetime

class MockEquityBroker:
    """
    A standalone SQLite-based broker for Traditional Equities.
    Simulates buying/selling stocks with realistic fees and PnL calculation locally.
    """
    
    def __init__(self, db_path: str = "storage/equity_trades.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.fee_rate = 0.001 # 0.1% per trade (realistic for traditional brokers)
        self.initial_balance = 10000.0
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS equity_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    size_shares REAL NOT NULL,
                    side TEXT NOT NULL, -- LONG / SHORT
                    status TEXT NOT NULL, -- OPEN / CLOSED
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    exit_price REAL,
                    profit_loss REAL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS equity_wallet (
                    balance REAL NOT NULL
                )
            ''')
            if conn.execute("SELECT COUNT(*) FROM equity_wallet").fetchone()[0] == 0:
                conn.execute("INSERT INTO equity_wallet (balance) VALUES (?)", (self.initial_balance,))
                
    def get_balance(self) -> float:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT balance FROM equity_wallet").fetchone()[0]

    def open_position(self, ticker: str, price: float, amount_usd: float, side: str = "LONG") -> bool:
        with sqlite3.connect(self.db_path) as conn:
            balance = self.get_balance()
            if balance < amount_usd:
                return False
                
            shares = (amount_usd * (1 - self.fee_rate)) / price
            
            conn.execute(
                "UPDATE equity_wallet SET balance = balance - ?",
                (amount_usd,)
            )
            
            conn.execute(
                "INSERT INTO equity_positions (ticker, entry_price, size_shares, side, status, opened_at) VALUES (?, ?, ?, ?, 'OPEN', ?)",
                (ticker, price, shares, side, datetime.utcnow().isoformat())
            )
            return True

    def close_position(self, position_id: int, exit_price: float) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            pos = conn.execute("SELECT ticker, entry_price, size_shares, side FROM equity_positions WHERE id = ? AND status = 'OPEN'", (position_id,)).fetchone()
            if not pos:
                return False
                
            ticker, entry_price, size_shares, side = pos
            value_at_exit = size_shares * exit_price
            value_after_fees = value_at_exit * (1 - self.fee_rate)
            
            invested = size_shares * entry_price
            
            if side == 'LONG':
                pnl = value_after_fees - invested
            else:
                pnl = invested - value_after_fees
                
            conn.execute(
                "UPDATE equity_positions SET status = 'CLOSED', closed_at = ?, exit_price = ?, profit_loss = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), exit_price, pnl, position_id)
            )
            
            conn.execute(
                "UPDATE equity_wallet SET balance = balance + ?",
                (invested + pnl,)
            )
            return True
            
    def get_open_positions(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute("SELECT * FROM equity_positions WHERE status = 'OPEN'").fetchall()]
