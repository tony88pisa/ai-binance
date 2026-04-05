"""
Fiscal Reporter — Generatore Automatico Rendiconto Fiscale Italiano.

Conforme al Paper (Sez. 7.2):
- Quadro W (monitoraggio detenzione crypto estere)
- IVAFE/IVCA (0.20% patrimoniale su portafogli esteri)
- Tassazione plusvalenze crypto al 33%
- Genera CSV e JSON pronto per il commercialista

Genera snapshot automatici al 1 Gennaio e 31 Dicembre di ogni anno.
"""

import csv
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("modules.fiscal_reporter")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports" / "fiscal"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Costanti fiscali italiane 2026
CRYPTO_TAX_RATE = 0.33          # Aliquota plusvalenze crypto
IVAFE_RATE = 0.002              # 0.20% patrimoniale IVAFE/IVCA
IVAFE_MIN_THRESHOLD = 12.00     # Soglia minima di versamento IVAFE


class FiscalReporter:
    """Gestisce la reportistica fiscale automatica per il bot."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(PROJECT_ROOT / "storage" / "v8_platform.sqlite")
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        """Crea la tabella fiscal_snapshots se non esiste."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fiscal_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_date TEXT NOT NULL,
                    snapshot_type TEXT NOT NULL,
                    portfolio_value_eur REAL NOT NULL,
                    initial_capital_eur REAL NOT NULL,
                    gross_profit_eur REAL NOT NULL,
                    tax_reserve_33pct REAL NOT NULL,
                    ivafe_due REAL NOT NULL,
                    ivafe_exempt INTEGER NOT NULL,
                    net_equity_eur REAL NOT NULL,
                    open_positions_json TEXT,
                    exchange_name TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def take_snapshot(self, portfolio_value: float, initial_capital: float,
                      open_positions: list = None, exchange_name: str = "binance",
                      snapshot_type: str = "periodic"):
        """
        Scatta una 'fotografia fiscale' del portafoglio.
        Deve essere chiamato automaticamente al 1/1 e 31/12, e periodicamente.

        Args:
            portfolio_value: Valore totale attuale del portafoglio in EUR/USDT
            initial_capital: Capitale iniziale investito
            open_positions: Lista di posizioni aperte [{"asset": "BTC", "value": 50.0}, ...]
            exchange_name: Nome dell'exchange (per Quadro W)
            snapshot_type: "jan1" | "dec31" | "periodic" | "manual"
        """
        gross_profit = max(0, portfolio_value - initial_capital)
        tax_reserve = gross_profit * CRYPTO_TAX_RATE

        # IVAFE: 0.20% del portafoglio, proporzionale ai giorni di detenzione
        # Per semplicità calcoliamo su base annua piena
        ivafe_annual = portfolio_value * IVAFE_RATE
        ivafe_exempt = 1 if ivafe_annual < IVAFE_MIN_THRESHOLD else 0

        net_equity = portfolio_value - tax_reserve

        now = datetime.now(timezone.utc).isoformat()
        positions_json = json.dumps(open_positions or [], ensure_ascii=False)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO fiscal_snapshots
                (snapshot_date, snapshot_type, portfolio_value_eur, initial_capital_eur,
                 gross_profit_eur, tax_reserve_33pct, ivafe_due, ivafe_exempt,
                 net_equity_eur, open_positions_json, exchange_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now[:10], snapshot_type, round(portfolio_value, 2),
                round(initial_capital, 2), round(gross_profit, 2),
                round(tax_reserve, 2), round(ivafe_annual, 4),
                ivafe_exempt, round(net_equity, 2), positions_json,
                exchange_name, now
            ))
            conn.commit()

        logger.info(
            f"📋 Snapshot fiscale salvato: Portafoglio={portfolio_value:.2f}€, "
            f"Profitto Lordo={gross_profit:.2f}€, Riserva Tasse={tax_reserve:.2f}€, "
            f"IVAFE={ivafe_annual:.4f}€ ({'ESENTE' if ivafe_exempt else 'DOVUTA'})"
        )

        return {
            "portfolio_value": portfolio_value,
            "gross_profit": gross_profit,
            "tax_reserve_33pct": tax_reserve,
            "ivafe_annual": ivafe_annual,
            "ivafe_exempt": bool(ivafe_exempt),
            "net_equity": net_equity
        }

    def export_csv(self, year: int = None) -> str:
        """
        Esporta tutti gli snapshot dell'anno in CSV per il commercialista.
        Ritorna il path del file generato.
        """
        if year is None:
            year = datetime.now().year

        output_path = REPORTS_DIR / f"quadro_w_{year}.csv"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM fiscal_snapshots
                WHERE snapshot_date LIKE ?
                ORDER BY snapshot_date ASC
            """, (f"{year}%",)).fetchall()

        if not rows:
            logger.warning(f"Nessuno snapshot fiscale trovato per l'anno {year}")
            return ""

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Data", "Tipo", "Valore Portafoglio (€)", "Capitale Iniziale (€)",
                "Profitto Lordo (€)", "Riserva Tasse 33% (€)", "IVAFE Dovuta (€)",
                "IVAFE Esente", "Equity Netta (€)", "Exchange", "Posizioni Aperte"
            ])
            for row in rows:
                writer.writerow([
                    row["snapshot_date"], row["snapshot_type"],
                    row["portfolio_value_eur"], row["initial_capital_eur"],
                    row["gross_profit_eur"], row["tax_reserve_33pct"],
                    row["ivafe_due"], "SI" if row["ivafe_exempt"] else "NO",
                    row["net_equity_eur"], row["exchange_name"],
                    row["open_positions_json"]
                ])

        logger.info(f"📄 Report CSV Quadro W esportato: {output_path}")
        return str(output_path)

    def export_json(self, year: int = None) -> str:
        """Esporta snapshot come JSON strutturato per integrazione software."""
        if year is None:
            year = datetime.now().year

        output_path = REPORTS_DIR / f"quadro_w_{year}.json"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM fiscal_snapshots
                WHERE snapshot_date LIKE ?
                ORDER BY snapshot_date ASC
            """, (f"{year}%",)).fetchall()

        data = {
            "anno_fiscale": year,
            "contribuente_note": "Generato automaticamente da Tengu V11 Fiscal Reporter",
            "normativa": {
                "aliquota_plusvalenze": "33%",
                "ivafe_ivca": "0.20%",
                "soglia_esenzione_ivafe": "12.00 EUR",
                "quadro": "W (ex RW)",
                "riferimento": "DAC8 / Legge di Bilancio 2026"
            },
            "snapshots": [dict(row) for row in rows]
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"📄 Report JSON Quadro W esportato: {output_path}")
        return str(output_path)

    def get_year_summary(self, year: int = None) -> dict:
        """Calcola il riepilogo fiscale annuale per il Quadro W e T."""
        if year is None:
            year = datetime.now().year

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Valore al 1 Gennaio
            jan1 = conn.execute("""
                SELECT portfolio_value_eur FROM fiscal_snapshots
                WHERE snapshot_date LIKE ? AND snapshot_type = 'jan1'
                ORDER BY created_at ASC LIMIT 1
            """, (f"{year}%",)).fetchone()

            # Valore al 31 Dicembre
            dec31 = conn.execute("""
                SELECT portfolio_value_eur FROM fiscal_snapshots
                WHERE snapshot_date LIKE ? AND snapshot_type = 'dec31'
                ORDER BY created_at DESC LIMIT 1
            """, (f"{year}%",)).fetchone()

            # Ultimo snapshot disponibile come fallback
            latest = conn.execute("""
                SELECT portfolio_value_eur FROM fiscal_snapshots
                WHERE snapshot_date LIKE ?
                ORDER BY created_at DESC LIMIT 1
            """, (f"{year}%",)).fetchone()

        val_jan1 = jan1["portfolio_value_eur"] if jan1 else 0.0
        val_dec31 = dec31["portfolio_value_eur"] if dec31 else (
            latest["portfolio_value_eur"] if latest else 0.0
        )

        annual_gain = val_dec31 - val_jan1
        tax_due = max(0, annual_gain) * CRYPTO_TAX_RATE
        ivafe = val_dec31 * IVAFE_RATE

        return {
            "anno": year,
            "valore_1_gennaio": round(val_jan1, 2),
            "valore_31_dicembre": round(val_dec31, 2),
            "plusvalenza_lorda": round(annual_gain, 2),
            "imposta_33pct": round(tax_due, 2),
            "ivafe_annuale": round(ivafe, 4),
            "ivafe_esente": ivafe < IVAFE_MIN_THRESHOLD,
            "nota": "Con portafogli < 6000€, IVAFE < 12€ → esente dal versamento materiale. Obbligo dichiarativo permane."
        }
