"""
V9.1 — Antigravity Command Center (Gemma 4 Optimized)
Dashboard con monitoraggio real-time RTX 5080 (16GB VRAM).
"""
import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import locali del progetto
from dashboard.routes_api import router as api_router, get_state, get_arena, get_logs
from storage.repository import Repository

app = FastAPI(title="Antigravity Command Center V9.1")
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

def get_gpu_info():
    """Interroga nvidia-smi per telemetria real-time (RTX 5080 Spec)."""
    try:
        # April 2026 Telemetry Protocol
        res = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], encoding='utf-8')
        used, total, util = res.strip().split(', ')
        return {"used": int(used), "total": int(total), "util": int(util)}
    except:
        return {"used": 0, "total": 16303, "util": 0}

# --- Commander HUD (PRIORITY) ---
@app.get("/commander", response_class=HTMLResponse)
def page_commander(request: Request):
    return templates.TemplateResponse("commander.html", {"request": request})

@app.get("/agents", response_class=HTMLResponse)
def page_agents(request: Request):
    return templates.TemplateResponse("agents.html", {"request": request})

@app.get("/trader", response_class=HTMLResponse)
def page_trader(request: Request):
    return templates.TemplateResponse("trader.html", {"request": request})

@app.get("/memory", response_class=HTMLResponse)
def page_memory(request: Request):
    return templates.TemplateResponse("memory.html", {"request": request})

@app.get("/logs", response_class=HTMLResponse)
def page_logs(request: Request):
    return templates.TemplateResponse("logs.html", {"request": request})

@app.get("/api/commander/data")
def get_commander_data():
    repo = Repository()
    state = get_state()
    arena = get_arena()
    gpu = get_gpu_info()
    
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
    
    # --- 2. EVOLUTION STAGE ---
    evolve_state = repo.get_service_state("autoevolve")
    stage = evolve_state.get('status', 'ACTIVE')
        
    return {
        "profit": {
            "total": state.get('pnl_eur', 0.0),
            "pct": state.get('pnl_pct', 0.0),
            "currency": state.get('currency', '€'),
            "history": pnl_history,
            "tradfi_pct": 0.0
        },
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
            "active_model": os.getenv("OLLAMA_MODEL", "gemma4:e4b")
        },
        "gpu_stats": gpu,
        "agents": arena,
        "reasoning": reasoning if reasoning else ["Analyzing market patterns for Gemma 4..."],
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
    
    # Se il frontend Node.js non esiste, il sistema deve reindirizzare alla dashboard python (Jinja2) predefinita
    from fastapi.responses import RedirectResponse
    @app.get("/", include_in_schema=False)
    def root_redirect():
        return RedirectResponse(url="/commander")

if __name__ == "__main__":
    import uvicorn
    # Porta di emergenza 8088 per bypassare i blocchi sulla 8087
    print(f"\n[AI INFO] Avvio Dashboard v9.1 - Gemma 4 Active on C: SSD")
    uvicorn.run(app, host="127.0.0.1", port=8088)
