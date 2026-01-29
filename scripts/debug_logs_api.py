# debug_logs_api.py
"""
FastAPI implementation for a centralized debug log API endpoint.
- POST /debug-logs: Ingest logs (JSON, unified schema)
- GET /debug-logs: Retrieve logs (with filters)
- DELETE /debug-logs: Clear all logs (admin only)
- TTL/auto-disable logic for production
- In-memory storage (can be swapped for DB)
"""
from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse, HTMLResponse
import os
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
from datetime import datetime, timedelta
import uuid
import os


app = FastAPI()

# Serve the debug_log_viewer.html UI at /debug-logs
@app.get("/debug-logs", response_class=HTMLResponse)
def serve_debug_log_viewer():
    html_path = os.path.join(os.path.dirname(__file__), "debug_log_viewer.html")
    with open(html_path, encoding="utf-8") as f:
        return f.read()

# CORS for local frontend UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory log store
LOGS: List[Dict[str, Any]] = []
MAX_LOGS = 10000
MAX_PAYLOAD_SIZE = 2048  # bytes
MAX_LOGS_PER_MIN = 100
LOG_SCHEMA_VERSION = "v1"

# TTL/auto-disable for production
API_ENABLED = os.environ.get("DEBUG_LOGS_API_ENABLED", "true").lower() == "true"
API_DISABLE_AT = None  # datetime
TTL_HOURS = int(os.environ.get("DEBUG_LOGS_API_TTL_HOURS", "24"))

# Simple admin token for DELETE (replace with real auth in prod)
ADMIN_TOKEN = os.environ.get("DEBUG_LOGS_ADMIN_TOKEN", str(uuid.uuid4()))

# Rate limiting (per source per minute)
RATE_LIMIT: Dict[str, List[datetime]] = {}

def is_api_enabled():
    global API_ENABLED, API_DISABLE_AT
    if not API_ENABLED:
        return False
    if API_DISABLE_AT and datetime.utcnow() > API_DISABLE_AT:
        API_ENABLED = False
        return False
    return True

@app.on_event("startup")
def set_ttl():
    global API_DISABLE_AT
    if os.environ.get("ENV", "dev") == "prod":
        API_DISABLE_AT = datetime.utcnow() + timedelta(hours=TTL_HOURS)

@app.post("/api/debug-logs")
async def ingest_log(request: Request):
    if not is_api_enabled():
        raise HTTPException(status_code=403, detail="Debug log API disabled.")
    if request.headers.get("content-length") and int(request.headers["content-length"]) > MAX_PAYLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Payload too large.")
    log = await request.json()
    # Basic schema/version check
    if log.get("log_schema_version") != LOG_SCHEMA_VERSION:
        raise HTTPException(status_code=400, detail="Invalid log schema version.")
    # Rate limit by source
    src = log.get("source", "unknown")
    now = datetime.utcnow()
    RATE_LIMIT.setdefault(src, [])
    RATE_LIMIT[src] = [t for t in RATE_LIMIT[src] if (now - t).seconds < 60]
    if len(RATE_LIMIT[src]) >= MAX_LOGS_PER_MIN:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})
    RATE_LIMIT[src].append(now)
    # Enforce log size
    if len(LOGS) >= MAX_LOGS:
        LOGS.pop(0)
    LOGS.append(log)
    return {"status": "ok"}

@app.get("/api/debug-logs")
async def get_logs(level: str = None, source: str = None, limit: int = 100):
    if not is_api_enabled():
        raise HTTPException(status_code=403, detail="Debug log API disabled.")
    logs = LOGS[-limit:]
    if level:
        logs = [l for l in logs if l.get("level") == level]
    if source:
        logs = [l for l in logs if l.get("source") == source]
    return logs

@app.delete("/api/debug-logs")
async def clear_logs(token: str = Depends(lambda: None)):
    if not is_api_enabled():
        raise HTTPException(status_code=403, detail="Debug log API disabled.")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    LOGS.clear()
    return {"status": "cleared"}

@app.get("/api/debug-logs/enabled")
async def api_status():
    return {"enabled": is_api_enabled(), "disable_at": API_DISABLE_AT}

# Health check
@app.get("/healthz")
async def health():
    return {"status": "ok"}
