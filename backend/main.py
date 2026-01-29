# Force reload
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .auth import router as auth_router
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid
import logging
import redis

# Context: Configure structured logging for backend observability

# Context: Configure structured logging for backend observability
import threading
import requests

class DebugLogAPIHandler(logging.Handler):
    def __init__(self, endpoint: str):
        super().__init__()
        self.endpoint = endpoint
        self.schema_version = "v2"

    def emit(self, record):
        try:
            payload = {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
                "level": record.levelname,
                "source": "backend",
                "service": record.name,
                "correlation_id": getattr(record, "correlation_id", None),
                "session_id": getattr(record, "session_id", None),
                "message": record.getMessage(),
                "meta": getattr(record, "meta", None),
                "log_schema_version": self.schema_version
            }
            # Derive log_category (same as /debug-logs endpoint)
            level = payload["level"].upper()
            message = payload["message"] or ""
            meta = payload["meta"] or {}
            log_category = "FLOW"
            if level == "ERROR" or ("status" in meta and str(meta["status"]).startswith("5")) or "auth fail" in message.lower() or "broker" in message.lower() or "infra" in message.lower():
                log_category = "CRITICAL"
            elif level == "WARN" or "market closed" in message.lower() or "fallback" in message.lower() or "retry" in message.lower():
                log_category = "WARNING"
            elif level == "DEBUG":
                log_category = "DEBUG"
            payload["log_category"] = log_category
            payload["log_schema_version"] = self.schema_version
            # Send asynchronously to avoid blocking
            threading.Thread(target=self._send, args=(payload,), daemon=True).start()
        except Exception:
            pass

    def _send(self, payload):
        try:
            requests.post(self.endpoint, json=payload, timeout=1)
        except Exception:
            pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("backend.log", mode='a', encoding='utf-8')
    ]
)
logger = logging.getLogger("api")
# Add handler to forward all logs to /debug-logs endpoint
logger.addHandler(DebugLogAPIHandler("http://localhost:8001/debug-logs"))

# Context: Middleware to generate unique Request IDs and log timing for every API call.
# This helps in debugging specific user requests by tracing the UUID.
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Extract query parameters for logging
        query_params = dict(request.query_params) if request.query_params else {}
        
        # Log Request Entry with more detail
        logger.info(f"\n{'='*120}")
        logger.info(f"📥 [{request_id}] {request.method:6s} {request.url.path}")
        if query_params:
            logger.debug(f"   Query params: {query_params}")
        logger.info(f"{'='*120}")
        
        response = await call_next(request)
        
        # Calculate duration
        process_time = (time.time() - start_time) * 1000
        
        # Color code status
        if response.status_code < 300:
            status_icon = "✅"
        elif response.status_code < 400:
            status_icon = "➡️"
        elif response.status_code < 500:
            status_icon = "⚠️"
        else:
            status_icon = "❌"
        
        # Log Response Exit with more detail
        logger.info(f"{'='*120}")
        logger.info(f"📤 [{request_id}] {status_icon} {response.status_code} - {process_time:.2f}ms")
        logger.info(f"{'='*120}\n")
        
        # Add Request ID to response headers for frontend tracing
        response.headers["X-Request-ID"] = request_id
        return response

app = FastAPI(title="Option Simulator API")

# Initialize Redis client for session storage
try:
    redis_client = redis.Redis(
        host='localhost', 
        port=6379, 
        db=0, 
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True
    )
    redis_client.ping()
    logger.info("✅ Redis connection successful for session storage")
    # Store redis_client for later use in auth
    import sys
    sys.modules['redis_client_global'] = redis_client
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    logger.error("❌ Cannot start without Redis. OAuth will fail!")
    raise

# Add Session Middleware for OAuth
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, session_cookie='session', max_age=3600)
app.add_middleware(LoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .database import engine, Base

@app.on_event("startup")
async def startup():
    logger.info("🚀 Application startup - initializing database")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created/verified successfully")
        
        # Initialize Redis (non-fatal if it fails)
        from .redis_client import redis_manager
        try:
            await redis_manager.connect()
            logger.info("✅ Redis connected successfully")
        except Exception as redis_error:
            logger.warning(f"⚠️ Redis connection failed: {redis_error}")
            logger.warning("⚠️ Paper trading features will NOT work without Redis!")
            logger.warning("⚠️ Please install Redis and restart the server")
        
        # Initialize Instrument Manager (Background Task)
        from .instrument_manager import instrument_manager
        import asyncio
        # Run in background so we don't block server startup/auth
        asyncio.create_task(instrument_manager.initialize())
        logger.info("⚡ Instrument Manager initialization started in background")
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {str(e)}", exc_info=True)
        # We don't raise here for instrument failure or Redis, but DB failure is critical.
        if "Instrument" not in str(e) and "Redis" not in str(e) and "redis" not in str(e).lower():
             raise

@app.on_event("shutdown")
async def shutdown():
    """Cleanup resources on shutdown"""
    logger.info("🛑 Application shutdown - cleaning up resources")
    try:
        from .redis_client import redis_manager
        await redis_manager.disconnect()
        logger.info("✅ Redis disconnected")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


from . import auth, broker
from .routers import trade, orders

app.include_router(auth.router)
app.include_router(broker.router)
app.include_router(trade.router)
app.include_router(orders.router)
logger.info("Auth, Broker, Trade routers included")

from .socket_manager import ws_router, debug_router
app.include_router(ws_router)
app.include_router(debug_router)
logger.info("WebSocket & Debug routers included")

from .market_data import router as market_router
app.include_router(market_router)
logger.info("Market Data router included")

from .database import engine, Base
from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse


# --- Debug Logs Endpoint ---
from fastapi import Body, Query
import re
import json
import os
from fastapi.responses import JSONResponse

LOG_FILE = os.environ.get("DEBUG_LOG_FILE", "backend.log")

def mask_email(email):
    if not email or "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 1:
        return "*" + "@" + domain
    return name[0] + "***@" + domain

def redact_sensitive(meta):
    if not isinstance(meta, dict):
        return meta, False
    redacted = False
    meta = dict(meta)
    for k in list(meta.keys()):
        if "token" in k.lower() or "credential" in k.lower() or "password" in k.lower():
            meta[k] = "[REDACTED]"
            redacted = True
        if "email" in k.lower() and isinstance(meta[k], str):
            meta[k] = mask_email(meta[k])
            redacted = True
    return meta, redacted

def derive_log_flow(service, message):
    s = (service or "").lower()
    m = (message or "").lower()
    if "auth" in s or "/auth" in m:
        return "AUTH"
    if "broker" in s or "/broker" in m:
        return "BROKER"
    if "market" in s or "/market" in m:
        return "MARKET"
    if "trade" in s or "/trade" in m:
        return "TRADE"
    if "ws" in s or "websocket" in s or "ws" in m:
        return "WEBSOCKET"
    if "system" in s or "infra" in s or "infra" in m:
        return "SYSTEM"
    return "OTHER"

@app.post("/debug-logs")
async def receive_debug_logs(payload: dict = Body(...)):
    """Receive frontend debug logs, add log_category, and write to backend log file."""
    # --- Derive log_category ---
    level = payload.get("level", "INFO").upper()
    message = payload.get("message", "")
    meta = payload.get("meta", {}) or {}
    log_category = "FLOW"  # Default
    if level == "ERROR" or ("status" in meta and str(meta["status"]).startswith("5")) or "auth fail" in message.lower() or "broker" in message.lower() or "infra" in message.lower():
        log_category = "CRITICAL"
    elif level == "WARN" or "market closed" in message.lower() or "fallback" in message.lower() or "retry" in message.lower():
        log_category = "WARNING"
    elif level == "DEBUG":
        log_category = "DEBUG"
    payload["log_category"] = log_category
    payload["log_schema_version"] = "v2"
    payload["log_flow"] = derive_log_flow(payload.get("service"), message)
    # Redact sensitive info
    meta, redacted = redact_sensitive(meta)
    payload["meta"] = meta
    if redacted:
        payload["redacted"] = True
    logger.info(f"[FRONTEND LOG] {payload}")
    return {"status": "ok"}

@app.get("/debug-logs")
async def get_debug_logs(
    limit: int = Query(100, ge=1, le=1000),
    level: str = Query(None),
    source: str = Query(None),
    log_category: str = Query(None),
    log_flow: str = Query(None),
    include_debug: bool = Query(False),
    only: str = Query(None),
    session_id: str = Query(None)
):
    """Return logs with summary, filtering, grouping, and redaction."""
    logs = []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in reversed(f.readlines()):
                if "[FRONTEND LOG]" in line:
                    try:
                        payload = json.loads(line.split("[FRONTEND LOG]",1)[1].strip().replace("'", '"'))
                    except Exception:
                        continue
                else:
                    # Try to parse backend logs if in JSON
                    try:
                        payload = json.loads(line.strip())
                    except Exception:
                        continue
                # Filtering
                if not include_debug and payload.get("level") == "DEBUG":
                    continue
                if level and payload.get("level") != level:
                    continue
                if source and payload.get("source") != source:
                    continue
                if log_category and payload.get("log_category") != log_category:
                    continue
                if log_flow and payload.get("log_flow") != log_flow:
                    continue
                if only and payload.get("log_category") != only.upper():
                    continue
                if session_id and payload.get("session_id") != session_id:
                    continue
                logs.append(payload)
                if len(logs) >= limit:
                    break
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    # --- Session summary ---
    summary = {
        "frontend_logs": sum(1 for l in logs if l.get("source") == "frontend"),
        "backend_logs": sum(1 for l in logs if l.get("source") == "backend"),
        "critical_count": sum(1 for l in logs if l.get("log_category") == "CRITICAL"),
        "warning_count": sum(1 for l in logs if l.get("log_category") == "WARNING"),
        "last_event_at": logs[0]["timestamp"] if logs else None,
        "health": "HEALTHY" if not any(l.get("log_category") == "CRITICAL" for l in logs) else "UNHEALTHY"
    }
    # Try to extract session_id, auth_status, broker_status, market_status from logs
    for l in logs:
        if l.get("session_id"):
            summary["session_id"] = l["session_id"]
        if l.get("meta"):
            m = l["meta"]
            if isinstance(m, dict):
                if "auth" in m:
                    summary["auth_status"] = m["auth"]
                if "broker" in m:
                    summary["broker_status"] = m["broker"]
                if "market" in m:
                    summary["market_status"] = m["market"]
    return {"summary": summary, "logs": logs}

@app.exception_handler(Exception)
async def global_exception_handler(request: FastAPIRequest, exc: Exception):
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}",
        exc_info=exc
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

@app.get("/")
def read_root():
    logger.debug("Root endpoint accessed")
    return {"status": "ok", "service": "Option Simulator Backend"}

# Remove Mock Router - Real implementation active
logger.info("🎯 Application initialization complete")

if __name__ == "__main__":
    logger.info("Starting uvicorn server...")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
