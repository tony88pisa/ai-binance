import sqlite3
from pathlib import Path
from datetime import datetime, timezone

class MockDeFiProtocol:
    """
    Simulatore Virtuale Vault DeFi Liquidity (Stile Aave / Uniswap V4).
    Mette in staking liquidità idle maturando un APY fittizio ma calcolato realisticamente.
    """
    def __init__(self, db_path="storage/defi_vaults.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Tasso annuo del 12% tipico nei bull market stablecoin farm
        self.apy_rate = 0.12 
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS vault_deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                deposited_at TEXT NOT NULL,
                last_compounded TEXT NOT NULL
            )''')
            
    def deposit(self, amount: float):
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO vault_deposits (amount, deposited_at, last_compounded) VALUES (?, ?, ?)",
                         (amount, now, now))
            conn.commit()
            
    def withdraw_all(self) -> float:
        """Ritira tutti i denari + yield."""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT SUM(amount) FROM vault_deposits").fetchone()[0] or 0.0
            conn.execute("DELETE FROM vault_deposits")
            conn.commit()
            return total
                         
    def compound_yield(self) -> float:
        """Composto continuo chiamato dal cron."""
        total_yield = 0.0
        now = datetime.now(timezone.utc)
        
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT id, amount, last_compounded FROM vault_deposits").fetchall()
            for r in rows:
                dep_id, amount, last_comp_str = r
                last_comp = datetime.fromisoformat(last_comp_str)
                seconds_passed = (now - last_comp).total_seconds()
                
                apy_per_second = self.apy_rate / (365 * 24 * 3600)
                yield_accrued = amount * (apy_per_second * seconds_passed)
                
                # Compound solo se supera minimo threshold per non sovraccaricare I/O SQLite
                if yield_accrued > 0.001:
                    total_yield += yield_accrued
                    conn.execute("UPDATE vault_deposits SET amount = amount + ?, last_compounded = ? WHERE id = ?",
                                 (yield_accrued, now.isoformat(), dep_id))
            conn.commit()
        return total_yield

    def get_total_staked(self) -> float:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT SUM(amount) FROM vault_deposits").fetchone()[0] or 0.0
