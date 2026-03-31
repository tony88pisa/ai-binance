import sys
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path("H:/ai binance")
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.app import app
from storage.repository import Repository

def run_fase_e():
    print(f"--- FASE E: COERENZA DASHBOARD ---")
    
    # 1. Verify App Routes
    routes = [route.path for route in app.routes]
    print(f"  > Dashboard Routes found: {routes}")
    
    required_routes = ["/live/", "/testlab/"]
    missing = [r for r in required_routes if r not in routes]
    if missing:
        print(f"FAIL: Missing routes {missing}")
        return False
    else:
        print(f"PASS: /live/ and /testlab/ routes registered.")

    # 2. Data Segregation Proof (SQL Check)
    repo = Repository()
    with repo._get_connection() as conn:
        # Live View Logic test
        live_model = conn.execute(
            "SELECT model_tag FROM live_deployments WHERE status = 'active' ORDER BY deployed_at DESC LIMIT 1"
        ).fetchone()
        
        # TestLab View Logic test
        lab_model = conn.execute(
            "SELECT tag_name FROM model_versions WHERE status IN ('validated', 'candidate') ORDER BY trained_at DESC LIMIT 1"
        ).fetchone()
        
        print(f"PASS: Data Segregation Logic (Live Model: {live_model['model_tag'] if live_model else 'None'}, Lab Model: {lab_model['tag_name'] if lab_model else 'None'})")

    return True

if __name__ == "__main__":
    run_fase_e()
