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

from dashboard.routes_api import router as api_router

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

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app.include_router(api_router)

# --- Page Routes ---
def no_cache(response: HTMLResponse):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/trading")

@app.get("/trading", response_class=HTMLResponse)
def page_trading(request: Request):
    return no_cache(templates.TemplateResponse("trading.html", {"request": request}))

@app.get("/logs", response_class=HTMLResponse)
def page_logs(request: Request):
    return no_cache(templates.TemplateResponse("logs.html", {"request": request}))

@app.get("/learning", response_class=HTMLResponse)
def page_learning(request: Request):
    return no_cache(templates.TemplateResponse("learning.html", {"request": request}))

@app.get("/system", response_class=HTMLResponse)
def page_system(request: Request):
    return no_cache(templates.TemplateResponse("system.html", {"request": request}))

@app.get("/health")
def health():
    from storage.repository import Repository
    from scheduler.session_manager import current_mode
    import json
    repo = Repository()
    state = repo.get_service_state("daemon")
    try:
        mode = json.loads(state.get("state_json", "{}")).get("mode", current_mode())
    except Exception:
        mode = current_mode()
    return {
        "status": "up",
        "daemon_mode": mode,
        "daemon_hb": state.get("last_heartbeat", "never"),
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8087)

