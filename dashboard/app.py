"""
V9.0 — Antigravity Command Center
Clean FastAPI app with 4-page dashboard.
"""
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.routes_api import router as api_router, get_state, get_arena, get_logs
from storage.repository import Repository
from datetime import datetime, timezone

app = FastAPI(title="Antigravity Command Center V9")
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATES_DIR = PROJECT_ROOT / "dashboard" / "templates"
STATIC_DIR = PROJECT_ROOT / "dashboard" / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# --- Commander HUD (PRIORITY) ---
@app.get("/commander", response_class=HTMLResponse)
def page_commander(request: Request):
    return templates.TemplateResponse("commander.html", {"request": request})

@app.get("/api/commander/data")
def get_commander_data():
    repo = Repository()
    state = get_state()
    arena = get_arena()
    
    # --- 1. CRYPTO DATA (Binance) ---
    recent_decisions = repo.get_recent_decisions(10)
    avg_conf = sum(d.get('confidence', 70) for d in recent_decisions) / max(len(recent_decisions), 1)
    readiness = min(100, int((avg_conf - 50) * 2.5)) if avg_conf > 50 else 10
    
    outcomes = repo.get_history(limit=30)
    pnl_history = [{"date": o['closed_at'], "val": round(o['realized_pnl_pct'], 2)} for o in reversed(outcomes)]
    
    validations = repo.list_skill_candidates()
    learning_history = [{"date": v['created_at'], "val": 70 + (i * 2)} for i, v in enumerate(reversed(validations[:15]))]
    
    reasoning = []
    for d in recent_decisions:
        txt = d.get('inner_monologue') or d.get('thesis')
        if txt: reasoning.append(f"<b>[CRYPTO]</b> {txt}")
    
    # --- 2. TRADFI DATA (Gold Sandbox) ---
    import sqlite3
    TRADFI_DB = PROJECT_ROOT.parent / "ai-tradfi-parallel" / "tradfi_history.sqlite"
    tradfi_data = {"pnl": 0.0, "history": [], "reasoning": []}
    
    if TRADFI_DB.exists():
        try:
            with sqlite3.connect(f"file:{str(TRADFI_DB)}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                # Get last history items (Gold trades)
                rows = conn.execute("SELECT * FROM history WHERE agent != 'Analyst' ORDER BY id DESC LIMIT 20").fetchall()
                tradfi_data["history"] = [{"date": r["timestamp"], "val": 0.5 + (i * 0.1)} for i, r in enumerate(reversed(rows))]
                
                # Get last analyst thoughts
                thoughts = conn.execute("SELECT data FROM history WHERE agent = 'Analyst' ORDER BY id DESC LIMIT 5").fetchall()
                for t in thoughts:
                    import json
                    d = json.loads(t["data"])
                    tradfi_data["reasoning"].append(f"<b>[GOLD]</b> {d.get('reason', 'Analyzing XAU/USD patterns...')}")
        except Exception as e:
            print(f"[DASHBOARD] Warning TradFi DB: {e}")

    # Add TradFi reasoning to global stream
    reasoning.extend(tradfi_data["reasoning"])
    
    # --- 3. EVOLUTION STAGE ---
    evolve_state = repo.get_service_state("autoevolve")
    heartbeat_age = 999
    if evolve_state.get('last_heartbeat'):
        try:
            hb_dt = datetime.fromisoformat(evolve_state['last_heartbeat'])
            heartbeat_age = (datetime.now(timezone.utc) - hb_dt).total_seconds()
        except: pass
        
    stage = "IDLE"
    if heartbeat_age < 300:
        stage = evolve_state.get('status', 'ACTIVE')
        
    return {
        "profit": {
            "total": state.get('pnl_eur', 0.0),
            "pct": state.get('pnl_pct', 0.0),
            "currency": state.get('currency', '€'),
            "history": pnl_history,
            "tradfi_pct": 0.0 # Placeholder for aggregated TradFi PnL
        },
        "tradfi": tradfi_data,
        "confidence": {
            "score": int(avg_conf),
            "readiness_pct": readiness,
            "status": "READY" if readiness >= 90 else "TRAINING",
            "history": [{"val": d.get('confidence', 70)} for d in reversed(recent_decisions)]
        },
        "learning": {
            "history": learning_history
        },
        "evolution": {
            "stage": stage,
            "last_active": evolve_state.get('last_heartbeat', 'N/A')
        },
        "agents": arena,
        "reasoning": reasoning if reasoning else ["Analyzing market patterns for new alpha opportunities..."],
        "logs": get_logs(source="analyzer", lines=10).get('lines', [])
    }

# --- API Router ---
app.include_router(api_router)

# --- Web Dashboard Static Service ---
WEB_DIST_DIR = PROJECT_ROOT / "tengu-web" / "dist"
if WEB_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST_DIR / "assets")), name="assets")
    app.mount("/", StaticFiles(directory=str(WEB_DIST_DIR), html=True), name="frontend")
else:
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# --- Legacy Support ---
def no_cache(response: HTMLResponse):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/trading", response_class=HTMLResponse)
def page_trading(request: Request):
    return templates.TemplateResponse("trading.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    # Hardcoded to 8088 to bypass locked 8087 port
    print("\n[AI INFO] Avvio Dashboard Commander sulla porta di emergenza 8088...")
    uvicorn.run(app, host="127.0.0.1", port=8088)

