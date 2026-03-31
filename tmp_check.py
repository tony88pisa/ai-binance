import sqlite3
import json
from pathlib import Path

db_path = Path('storage/v8_platform.sqlite')
if not db_path.exists():
    print('DB non trovato.')
else:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("\n" + "="*40)
    print("--- 📊 SYSTEM STATE ---")
    ss = conn.execute("SELECT * FROM service_state WHERE service='daemon'").fetchone()
    if ss:
        j = json.loads(ss['state_json'])
        print(f"Stato: {ss['status']}")
        print(f"Ultimo Heartbeat: {ss['last_heartbeat']}")
        print(f"Modalità: {j.get('mode')}")
        print(f"Wallet (sim): {j.get('wallet_eur', 0):.2f} EUR")
        print(f"PnL Totale:   {j.get('pnl_total', 0):.2f} EUR")
    
    print("\n--- 📈 TRADES OUTCOMES (Chiusi) ---")
    outcomes = conn.execute("SELECT COUNT(*) as cnt, SUM(realized_pnl_pct) as total_pnl, SUM(was_profitable) as wins FROM trade_outcomes").fetchone()
    cnt = outcomes["cnt"] or 0
    print(f"Trades Chiusi: {cnt}")
    if cnt > 0:
        winrate = (outcomes["wins"]/cnt)*100 if outcomes["wins"] else 0
        total_pnl = outcomes["total_pnl"] or 0
        print(f"Winrate: {winrate:.2f}%")
        print(f"Total PnL %: {total_pnl:.2f}%")
        
        print("\n--- ULTIMI 5 TRADES ---")
        recent = conn.execute("SELECT d.asset, d.action, o.realized_pnl_pct, o.was_profitable, o.closed_at FROM trade_outcomes o JOIN decisions d ON o.decision_id = d.id ORDER BY o.closed_at DESC LIMIT 5").fetchall()
        for r in recent:
            win_str = "WIN " if r["was_profitable"] else "LOSS"
            print(f"{r['closed_at'].split('.')[0]} | {r['asset']:>8} | {r['action']:<4} | {win_str} | PnL: {r['realized_pnl_pct']:.2f}%")
        
    print("\n--- 🟡 OPEN TRADES ---")
    open_trades = conn.execute("SELECT asset, action, timestamp FROM decisions WHERE status='OPEN'").fetchall()
    print(f"Trades Aperti: {len(open_trades)}")
    for ot in open_trades:
        print(f"- {ot['asset']} (Action: {ot['action']}, Since: {ot['timestamp'].split('.')[0]})")
    
    print("\n--- 🧠 EVOLUTION LAB ---")
    skills = conn.execute("SELECT COUNT(*) as cnt FROM skill_candidates").fetchone()
    promoted = conn.execute("SELECT COUNT(*) as cnt FROM skill_candidates WHERE status='promoted'").fetchone()
    print(f"Skill Generate: {skills['cnt']}")
    print(f"Skill Promosse: {promoted['cnt']}")
    
    print("\n" + "="*40)
