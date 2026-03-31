import sys
import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Imports are late to avoid circular issues
from dashboard.routes_live import router as live_router
from dashboard.routes_testlab import router as testlab_router
from dashboard.routes_panoramica import router as panoramica_router
from dashboard.routes_laboratorio import router as laboratorio_router
from dashboard.routes_debug import router as debug_router

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard.app-fixed")

app = FastAPI(title="Antigravity V8.3 Unified Engine")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static & Templates
# We assume dashboard/static exists
app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

# Register Routers
app.include_router(panoramica_router, prefix="", tags=["Centro di Controllo"])
app.include_router(laboratorio_router, prefix="/laboratorio", tags=["Laboratorio"])
app.include_router(live_router, prefix="/live", tags=["Live Dashboard"])
app.include_router(testlab_router, prefix="/testlab", tags=["TestLab Dashboard"])
app.include_router(debug_router, prefix="", tags=["Debug Console"])

@app.get("/health")
async def health_check():
    import datetime
    return {
        "timestamp": datetime.datetime.now().strftime("%d/%m/%2026 %H:%M:%S"),
        "status": "healthy",
        "version": "8.3.11",
        "module": "Unified Profitability Layer"
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Dashboard on port 8087...")
    uvicorn.run(app, host="0.0.0.0", port=8087)
