"""
TENGU V12 — BACKTEST CLI RUNNER
=================================
Uso:
  python run_backtest.py --symbol PEPE/USDT --days 30
  python run_backtest.py --symbol WIF/USDT --days 14 --timeframe 5m
  python run_backtest.py --symbol BONK/USDT --days 7 --no-walk-forward
"""
import sys
import argparse
import logging
from pathlib import Path

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai.backtester import Backtester, BacktestConfig, fetch_historical_ohlcv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BACKTEST] %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="TENGU V12 Backtester")
    parser.add_argument("--symbol", type=str, default="PEPE/USDT", help="Coppia di trading (es. PEPE/USDT)")
    parser.add_argument("--days", type=int, default=30, help="Giorni di storia da testare")
    parser.add_argument("--timeframe", type=str, default="5m", help="Timeframe (5m, 15m, 1h)")
    parser.add_argument("--capital", type=float, default=100.0, help="Capitale iniziale in USDT")
    parser.add_argument("--min-score", type=int, default=70, help="Score minimo per entrare")
    parser.add_argument("--min-confidence", type=int, default=70, help="Confidence minima")
    parser.add_argument("--no-walk-forward", action="store_true", help="Disabilita walk-forward split")
    parser.add_argument("--exchange", type=str, default="binance", help="Exchange ccxt da usare")
    parser.add_argument("--save", type=str, default=None, help="Path per salvare report JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("  TENGU V12 — BACKTESTER CLI")
    print("=" * 60)
    print(f"  Symbol:     {args.symbol}")
    print(f"  Days:       {args.days}")
    print(f"  Timeframe:  {args.timeframe}")
    print(f"  Capital:    ${args.capital:.2f}")
    print(f"  Min Score:  {args.min_score}")
    print(f"  Walk-Fwd:   {'NO' if args.no_walk_forward else 'YES'}")
    print("=" * 60)

    # 1. Scarica dati storici
    print("\n[...] Scaricamento dati storici...")
    df = fetch_historical_ohlcv(
        symbol=args.symbol,
        timeframe=args.timeframe,
        days=args.days,
        exchange_name=args.exchange,
    )
    print(f"[OK] {len(df)} candele scaricate")

    # 2. Configura ed esegui backtest
    config = BacktestConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        initial_capital=args.capital,
        min_score=args.min_score,
        min_confidence=args.min_confidence,
        walk_forward=not args.no_walk_forward,
    )
    
    print("\n[...] Esecuzione backtest...")
    backtester = Backtester(config)
    report = backtester.run(df)

    # 3. Stampa risultati
    report.print_summary()

    # 4. Salva se richiesto
    if args.save:
        save_path = Path(args.save)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(report.to_json(), encoding="utf-8")
        print(f"[SAVED] Report salvato in: {save_path}")
    else:
        # Default: salva in reports/
        reports_dir = PROJECT_ROOT / "reports"
        reports_dir.mkdir(exist_ok=True)
        filename = f"backtest_{args.symbol.replace('/', '_')}_{args.days}d.json"
        save_path = reports_dir / filename
        save_path.write_text(report.to_json(), encoding="utf-8")
        print(f"[SAVED] Report salvato in: {save_path}")


if __name__ == "__main__":
    main()
