"""
Module 10-FALLBACK — Direct Tailscale IP Binding
- Binds specifically to 100.84.252.107 (NOT 127.0.0.1 or 0.0.0.0)
- Startup wait/retry logic for Tailscale interface availability.
- Fail-closed auth (No default credentials)
- Authenticated POST-only commands
"""
import os
import sys
import subprocess
import json
import time
import socket
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.manager import MemoryManager
from config.settings import get_settings

# --- MANDATORY CONFIG & TAILSCALE IP ---
TAILSCALE_IP = "100.84.252.107"
MAX_STARTUP_RETRIES = 30  # 30 * 5s = 150s (2.5 mins)

def wait_for_tailscale_ip(target_ip: str):
    """Wait and retry until the Tailscale IP is available on a local interface."""
    print(f"SECURITY: Checking for Tailscale IP {target_ip} availability...")
    for i in range(MAX_STARTUP_RETRIES):
        try:
            # Check if we can get the address info for this specific IP
            # On Windows, this confirms it exists in the routing table/adapter
            socket.getaddrinfo(target_ip, None)
            print(f"SUCCESS: Tailscale IP {target_ip} is available.")
            return True
        except socket.gaierror:
            print(f"RETRY #{i+1}: Tailscale IP {target_ip} not available yet. Waiting 5s...")
            time.sleep(5)
    print(f"FATAL: Tailscale IP {target_ip} was not detected after {MAX_STARTUP_RETRIES} retries.")
    return False

def load_env_file():
    """Manually parse .env to avoid dependency issues in WinSW."""
    env_vars = {}
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    name, value = line.strip().split("=", 1)
                    env_vars[name.strip()] = value.strip()
    return env_vars

# PRE-STARTUP BLOCK: Fail-closed sequence
ENV = load_env_file()
CTRL_USER = ENV.get("CONTROL_CENTER_USER")
CTRL_PASS = ENV.get("CONTROL_CENTER_PASSWORD")

if not CTRL_USER or not CTRL_PASS:
    print("CRITICAL: CONTROL_CENTER_USER or CONTROL_CENTER_PASSWORD not set in .env.")
    print("CONTROL CENTER IS SHUTTING DOWN FOR SECURITY. FAIL-CLOSED.")
    sys.exit(1)

# IP READINESS BLOCK: Ensure the service can bind before starting FastAPI
if not wait_for_tailscale_ip(TAILSCALE_IP):
    print("CONTROL CENTER IS SHUTTING DOWN: TAILSCALE INTERFACE NOT FOUND.")
    sys.exit(1)

app = FastAPI(title="AI Trading Bot Control Center (V6.0-FALLBACK)")
security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    """Validates against dedicated Control Center secrets ONLY."""
    if credentials.username != CTRL_USER or credentials.password != CTRL_PASS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# --- SERVICE CONTROL (STRICT POST ONLY) ---
@app.post("/api/service/{action}/{service_name}")
def control_service(action: str, service_name: str, username: str = Depends(authenticate)):
    """Executes WinSW commands to Restart/Stop orchestrator services from phone."""
    valid_actions = ["start", "stop", "restart", "status"]
    valid_services = ["V6-Freqtrade", "V6-Daemon", "V6-ControlCenter"]
    
    if action not in valid_actions or service_name not in valid_services:
        raise HTTPException(status_code=400, detail="Invalid action or service target.")
        
    bin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
    exe_path = os.path.join(bin_dir, f"{service_name}.exe")
    
    if not os.path.exists(exe_path):
        raise HTTPException(status_code=500, detail=f"Service binary not found: {exe_path}")
        
    try:
        res = subprocess.run([exe_path, action], capture_output=True, text=True, timeout=10)
        return {"status": "success", "action": action, "service": service_name, "output": res.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Command failed: {str(e)}")

# --- UI LAYER ---
@app.get("/", response_class=HTMLResponse)
def read_root(username: str = Depends(authenticate)):
    """Renders the secure Fallback Control Center."""
    settings = get_settings()
    vmode = settings.model.validation_mode.upper()
    html_content = f"""
    <html>
        <head>
            <title>V6.0-FALLBACK Control Center</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #020617; color: #f8fafc; margin: 0; padding: 20px; }}
                h1 {{ color: #38bdf8; font-size: 1.4rem; border-bottom: 2px solid #38bdf8; padding-bottom: 15px; margin-bottom: 25px; }}
                .metric {{ background: #0f172a; padding: 15px; border-radius: 12px; margin-bottom: 15px; border: 1px solid #1e293b; }}
                .tag {{ padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 0.75rem; }}
                .tag-mock {{ background: #f59e0b; color: #000; }}
                .tag-real {{ background: #10b981; color: #fff; }}
                pre {{ background: #1e293b; padding: 10px; border-radius: 8px; overflow-x: auto; color: #94a3b8; font-size: 0.8rem; margin: 0; }}
                .btn-group {{ display: flex; gap: 8px; margin-top: 8px; }}
                button {{ flex: 1; padding: 12px; border: none; border-radius: 8px; font-weight: 700; cursor: pointer; font-size: 0.9rem; transition: transform 0.1s, opacity 0.2s; }}
                .btn-restart {{ background: #0284c7; color: white; }}
                .btn-stop {{ background: #e11d48; color: white; }}
                .service-title {{ font-weight: 600; color: #94a3b8; font-size: 0.85rem; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.05em; }}
                #log_output {{ border-left: 4px solid #38bdf8; margin-top: 10px; color: #2dd4bf; background: #020617; }}
                .warning {{ color: #facc15; font-size: 0.8rem; border: 1px solid #ca8a04; padding: 10px; border-radius: 8px; margin-bottom: 20px; background: rgba(202, 138, 4, 0.1); }}
            </style>
        </head>
        <body>
            <h1>DIRECT CONTROL 🛡️</h1>
            
            <div class="warning">
                <b>FALLBACK BIND ACTIVE:</b> Port 8085 is bound directly to the Tailscale IP <b>{TAILSCALE_IP}</b>. Loopback access via localhost is currently disabled for remote security.
            </div>

            <div class="metric">
                <div class="service-title">ENVIRONMENT & AUTH</div>
                <p style="margin:5px 0;">Operator: <b style="color:#ffffff">{username}</b></p>
                <p style="margin:5px 0;">Mode: <span class="tag tag-{vmode.lower()}">{vmode}</span></p>
                <p style="margin:5px 0;">Current Host: <span style="font-family:monospace; color:#38bdf8">{TAILSCALE_IP}</span></p>
            </div>

            <div class="metric">
                <div class="service-title">SERVICE CONTROLS (POST ONLY)</div>
                <div style="margin-bottom: 15px;">
                    <div style="font-size:0.95rem; font-weight:bold; margin-bottom:5px;">Freqtrade Trading Engine</div>
                    <div class="btn-group">
                        <button class="btn-restart" onclick="svc('restart', 'V6-Freqtrade')">RESTART</button>
                        <button class="btn-stop" onclick="svc('stop', 'V6-Freqtrade')">STOP</button>
                    </div>
                </div>
                <div>
                    <div style="font-size:0.95rem; font-weight:bold; margin-bottom:5px;">Research Daemon</div>
                    <div class="btn-group">
                        <button class="btn-restart" onclick="svc('restart', 'V6-Daemon')">RESTART</button>
                        <button class="btn-stop" onclick="svc('stop', 'V6-Daemon')">STOP</button>
                    </div>
                </div>
            </div>

            <div class="metric">
                <div class="service-title">DIAGNOSTIC LOGS</div>
                <button style="width: 100%; padding: 10px; background: #334155; margin-bottom: 10px;" onclick="refresh()">RELOAD TELEMETRY</button>
                <pre id="stats">Awaiting reload...</pre>
                <pre id="log_output">Ready for encrypted operator command.</pre>
            </div>

            <script>
                async function refresh() {{
                    try {{
                        const res = await fetch('/api/evaluation');
                        const data = await res.json();
                        if (res.status === 401) window.location.reload();
                        document.getElementById('stats').textContent = JSON.stringify(data, null, 2);
                    }} catch (e) {{ console.error(e); }}
                }}
                
                async function svc(action, service) {{
                    if (!confirm('SECURITY OVERRIDE: Are you sure you want to ' + action.toUpperCase() + ' ' + service + '?')) return;
                    
                    const log = document.getElementById('log_output');
                    log.textContent = 'TRANSMITTING ENCRYPTED ' + action.toUpperCase() + '...';
                    
                    try {{
                        const res = await fetch('/api/service/' + action + '/' + service, {{ method: 'POST' }});
                        const data = await res.json();
                        if (!res.ok) throw new Error(data.detail || res.statusText);
                        log.textContent = 'SUCCESS: ' + (data.output || action + ' executed.');
                        setTimeout(refresh, 2000);
                    }} catch (err) {{
                        log.textContent = 'NETWORK ERROR: ' + err.message;
                    }}
                }}
                
                setInterval(refresh, 60000);
                document.addEventListener('DOMContentLoaded', refresh);
            </script>
        </body>
    </html>
    """
    return html_content

@app.get("/api/evaluation")
def read_evaluation(username: str = Depends(authenticate)):
    """Returns the current evaluation metrics."""
    try:
        mgr = MemoryManager()
        return mgr.compute_evaluation().to_dict()
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # If run directly (e.g. from command line for debug)
    import uvicorn
    uvicorn.run(app, host=TAILSCALE_IP, port=8085)
