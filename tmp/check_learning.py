import sys
from pathlib import Path
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from storage.repository import Repository

def analyze_learning():
    repo = Repository()
    
    print("\n=== STATUS TRADING ===")
    open_decisions = repo.get_open_decisions()
    print(f"Posizioni aperte attualmente: {len(open_decisions)}")
    for d in open_decisions:
        print(f" - {d['asset']} : {d['action']} : Confidence {d['confidence']}")
        
    with repo._conn() as conn:
        print("\n=== EVOLUZIONE & APPRENDIMENTO ===")
        # Count outcomes
        outcomes_count = conn.execute("SELECT COUNT(*) as c FROM trade_outcomes").fetchone()["c"]
        print(f"Trade elaborati dallo storico (per imparare): {outcomes_count}")
        
        # Check skill candidates
        skills = conn.execute("""
            SELECT skill_id, source, validation_status as status, created_at 
            FROM skill_candidates 
            ORDER BY created_at DESC 
            LIMIT 5
        """).fetchall()
        
        print(f"\nUltime 5 Skill generate:")
        if not skills:
            print(" Nessuna skill generata ancora (Lab Cycle potrebbe non aver ancora girato o non ci sono abbastanza outcome).")
        else:
            for s in skills:
                print(f" - [{s['status'].upper()}] {s['skill_id']} (Da: {s['source']}) - {s['created_at']}")
                
        # Promozioni
        approved = conn.execute("SELECT COUNT(*) as c FROM skill_candidates WHERE validation_status = 'approved'").fetchone()["c"]
        print(f"\nSkill Approvate e passate in Produzione: {approved}")

        # Check performance
        perf = conn.execute("""
            SELECT SUM(realized_pnl_pct) as total_pnl,
                   SUM(CASE WHEN was_profitable=1 THEN 1 ELSE 0 END) as wins,
                   COUNT(*) as trades
            FROM trade_outcomes
        """).fetchone()
        
        if perf and perf['trades'] > 0:
            winrate = (perf['wins'] / perf['trades']) * 100
            print(f"\nPerformance AI Storica globale:")
            print(f" - Win Rate: {winrate:.1f}% ({perf['wins']}/{perf['trades']})")
        else:
            print("\nPerformance AI Storica globale: Nessun dato.")

if __name__ == "__main__":
    analyze_learning()
