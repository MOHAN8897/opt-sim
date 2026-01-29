import asyncio
import json
import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import List, Dict, Set
import logging
from .auth import get_current_user_token, SESSION_TIMEOUT_MINUTES
from .models import User, UpstoxAccount, UpstoxStatus
from .database import get_db
from sqlalchemy.future import select
from datetime import datetime, timedelta
from .config import settings
from jose import jwt
from .broker import decrypt
from .market_feed import UpstoxFeedBridge

# Configure Logger
logger = logging.getLogger("api.websocket")

ws_router = APIRouter(prefix="/ws", tags=["websocket"])
debug_router = APIRouter(prefix="/api", tags=["debug"])

class ConnectionManager:
    def __init__(self):
        # Map: UserEmail -> List[WebSocket]
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Map: WebSocket -> BridgeInstance
        self.bridges: Dict[WebSocket, UpstoxFeedBridge] = {}

    async def connect(self, websocket: WebSocket, user_email: str, bridge: UpstoxFeedBridge):
        # await websocket.accept()  <-- Managed by endpoint now
        if user_email not in self.active_connections:
            self.active_connections[user_email] = []
        self.active_connections[user_email].append(websocket)
        self.bridges[websocket] = bridge
        logger.info(f"WebSocket connected for user: {user_email}")

    async def disconnect(self, websocket: WebSocket, user_email: str):
        if user_email in self.active_connections:
            if websocket in self.active_connections[user_email]:
                self.active_connections[user_email].remove(websocket)
            if not self.active_connections[user_email]:
                del self.active_connections[user_email]
        
        # Stop Bridge
        if websocket in self.bridges:
            await self.bridges[websocket].stop()
            del self.bridges[websocket]
            
        logger.info(f"WebSocket disconnected for user: {user_email}")

    async def disconnect_user(self, user_email: str, reason: str = "Session Expired"):
        """Force disconnect all sockets for a user"""
        if user_email in self.active_connections:
            # Copy list to iterate safely
            for connection in list(self.active_connections[user_email]):
                try:
                    await connection.close(code=1008, reason=reason)
                    # Trigger standard disconnect cleanup
                    await self.disconnect(connection, user_email) 
                except Exception as e:
                    logger.error(f"Error closing socket for {user_email}: {e}")
            logger.info(f"Force disconnected user {user_email}: {reason}")

manager = ConnectionManager()

async def get_user_from_token(token: str, db):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email = payload.get("sub")
        if not email: return None
        
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()
        return user
    except Exception as e:
        logger.error(f"WS Auth Error: {e}")
        return None

def _generate_feed_debug():
    """Shared logic for generating feed debug stats"""
    stats = []
    
    # Iterate over all active bridges
    for ws, bridge in manager.bridges.items():
        try:
            # 1. State & Identity
            current_state = "RESETTING" if bridge.reset_in_progress else bridge.connection_state
            
            # 2. Subscription Health
            active_keys = list(bridge.subscriptions)
            sub_count = len(active_keys)
            expected_count = 31 # Standard window
            missing_count = max(0, expected_count - sub_count)
            starvation = missing_count > 5 and current_state == "LIVE"
            
            # 3. Time Calculations
            now = datetime.now()
            state_dur = (now - bridge.state_since_ts).total_seconds()
            
            # 4. Tick Health
            tm = bridge.tick_metrics
            ticks_1s = tm.get("count_1s", 0)
            # Extrapolate 5s if needed or use stored
            ticks_5s = int(tm.get("count_5s", 0) + ticks_1s) 
            
            # 5. Frontend Safety
            should_render = current_state in ["LIVE", "RESETTING"]
            should_clear = current_state in ["CLOSED", "FAILED"]
            safety_reason = f"State is {current_state}"
            
            # 6. Reset Diagnostics
            cooldown_rem = 0
            if bridge.last_reset_ts > 0:
                 elapsed = now.timestamp() - bridge.last_reset_ts
                 cooldown_rem = max(0, 5.0 - elapsed)

            feed_doc = {
                "identity": {
                    "feed_id": getattr(bridge, "feed_id", "unknown"),
                    "underlying": bridge.underlying_key,
                    "expiry": bridge.instrument_expiry,
                    "strike_step": bridge.strike_step
                },
                "state": {
                    "status": current_state,
                    "since": bridge.state_since_ts.isoformat(),
                    "duration_sec": round(state_dur, 2),
                    "is_market_open": bridge.is_market_open()
                },
                "atm_window": {
                    "current_atm": bridge.current_atm,
                    "window_size": 15, 
                    "live_strikes_count": len(bridge.build_live_strikes(bridge.current_atm or 0, bridge.strike_step or 50) if bridge.current_atm else []),
                    "expected_count": expected_count
                },
                "subscriptions": {
                    "count": sub_count,
                    "keys": active_keys, 
                    "starvation_detected": starvation,
                    "missing_keys_est": missing_count
                },
                "reset_diagnostics": {
                    "in_progress": bridge.reset_in_progress,
                    "locked": bridge.session_locked,
                    "last_reset": {
                        "reason": getattr(bridge, "last_reset_reason", "None"),
                        "at": datetime.fromtimestamp(bridge.last_reset_ts).isoformat() if bridge.last_reset_ts else None
                    },
                    "cooldown": {
                        "active": cooldown_rem > 0,
                        "remaining_sec": round(cooldown_rem, 1)
                    }
                },
                "tick_health": {
                    "ticks_last_1s": ticks_1s,
                    "ticks_last_5s": ticks_5s,
                    "last_tick_ts": datetime.fromtimestamp(tm.get("last_tick_ts", 0)).isoformat() if tm.get("last_tick_ts") else None,
                    "last_broker_ts": tm.get("last_broker_ts", 0),
                    "max_tick_gap_ms": tm.get("max_gap_ms", 0)
                },
                "buffer": {
                    "size": len(bridge.update_buffer),
                    "broadcast_interval_ms": 50,
                    "dropped_last_10s": getattr(bridge, "dropped_updates_count", 0)
                },
                "frontend_safety": {
                    "should_render": should_render,
                    "should_clear": should_clear,
                    "reason": safety_reason
                }
            }
            stats.append(feed_doc)
            
        except Exception as e:
            stats.append({"error": str(e), "trace": "Error generating stats for bridge"})

    return {
        "timestamp": datetime.now().isoformat(),
        "feed_count": len(stats),
        "feeds": stats
    }

@ws_router.get("/debug/feed")
async def get_feed_debug_ws():
    """Access debug info via WS path"""
    return _generate_feed_debug()

@debug_router.get("/debug/feed")
async def get_feed_debug_api():
    """Access debug info via API path (CI/Curl friendly)"""
    return _generate_feed_debug()

@ws_router.websocket("/market-data")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    user_email = "unknown"
    # 1. Accept Connection First (Standard Pattern)
    await websocket.accept()
    
    # 2. Extract Token (Cookie Priority)
    if not token:
        token = websocket.cookies.get("access_token")
    
    if not token:
        logger.warning("WS Connect failed: No token provided")
        await websocket.close(code=1008, reason="Missing Authentication")
        return

    # 3. Authenticate & Setup Session
    from .database import AsyncSessionLocal
    
    try:
        async with AsyncSessionLocal() as db:
            user = await get_user_from_token(token, db)
            
            if not user:
                logger.warning("WS Connect failed: Invalid token")
                await websocket.close(code=1008, reason="Invalid Token")
                return
                
            # Check Inactivity
            now = datetime.utcnow()
            if user.last_active:
                 last_active = user.last_active.replace(tzinfo=None) if user.last_active.tzinfo else user.last_active
                 time_diff = (now - last_active).total_seconds()
                 if time_diff > (SESSION_TIMEOUT_MINUTES * 60):
                     await websocket.close(code=1008, reason="Session Expired")
                     return

            # Check Broker Status
            stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
            result = await db.execute(stmt)
            account = result.scalars().first()
            
            
            if not account or account.status != UpstoxStatus.TOKEN_VALID or not account.access_token:
                 if not account:
                     logger.warning(f"WS Rejected: No Upstox account for user {user.email}")
                 elif account.status != UpstoxStatus.TOKEN_VALID:
                     logger.warning(f"WS Rejected: Broker status is {account.status} (not TOKEN_VALID) for user {user.email}")
                 elif not account.access_token:
                     logger.warning(f"WS Rejected: No access_token in database for user {user.email}")
                 
                 await websocket.close(code=1008, reason="Broker Not Connected")
                 return
                 
            access_token = decrypt(account.access_token)
            api_key = decrypt(account.api_key)
            
            # Register Connection
            user_email = user.email
            await manager.connect(websocket, user_email, None)
            
            # Update Activity
            user.last_active = now
            await db.commit()
            
            # ⚡ IMMEDIATE ACKNOWLEDGMENT to prevent frontend timeout
            # Send this BEFORE starting Upstox connection (which takes 1-2 seconds)
            logger.info("[ws] Sending immediate WS_CONNECTED acknowledgment to frontend")
            try:
                await websocket.send_text(json.dumps({
                    "type": "WS_CONNECTED",
                    "msg": "WebSocket authenticated, connecting to market feed..."
                }))
            except Exception as e:
                logger.error(f"Failed to send WS_CONNECTED ack: {e}")
            
            # 4. START LIFECYCLE (Keep session scope? No, session is closed after this block)
            # We need to pass the access_token to the bridge, which runs independently.
            # The bridge doesn't need DB access usually, just API access.
            
    except Exception as e:
        logger.error(f"WS Auth/Setup Error: {e}")
        await websocket.close(code=1011, reason="Internal Server Error")
        return

    # Define Callback for Feed Unavailable (403 - Entitlement Issue)
    async def mark_feed_unavailable():
        logger.error(f"Marking feed UNAVAILABLE for user {user.email} (403 entitlement failure)")
        
        # 🔒 CRITICAL: Validate WebSocket state before sending
        from starlette.websockets import WebSocketState
        if websocket.client_state != WebSocketState.CONNECTED:
            logger.warning(f"⚠️ Cannot send FEED_UNAVAILABLE - WebSocket already closed/closing")
            # Still update DB even if we can't notify frontend
        else:
            try:
                 # 📌 5️⃣ FRONTEND ↔ BACKEND SIGNALING
                 logger.info(f"[ws] Sending FEED_UNAVAILABLE event to frontend")
                 await websocket.send_text(json.dumps({
                     "type": "FEED_UNAVAILABLE", 
                     "msg": "Market Data Feed permission not enabled in Upstox. Check Developer Console."
                 }))
            except Exception as send_err:
                 logger.error(f"Failed to send FEED_UNAVAILABLE event: {send_err}")
                 
        # 📌 4️⃣ DATABASE STATE TRANSITIONS (always attempt)
        try:
             async with AsyncSessionLocal() as db_session:
                 logger.info(f"[db] Checking feed_entitlement status")
                 stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
                 res = await db_session.execute(stmt)
                 acc = res.scalars().first()
                 if acc:
                     # IDEMPOTENCY GUARD: Prevent repeated updates
                     if acc.feed_entitlement == 0:
                         logger.info(f"[db] Feed already marked UNAVAILABLE – skipping DB update")
                         return
                     
                     logger.info(f"[db] Updating feed_entitlement → 0 (UNAVAILABLE)")
                     acc.feed_entitlement = 0  # Feed unavailable
                     # Do NOT touch access_token or status - they remain valid for REST
                     db_session.add(acc)
                     await db_session.commit()  # CRITICAL: Commit changes
                     logger.info(f"[db] ✅ Feed entitlement persisted successfully")
                 else:
                     logger.warning("No account found to mark feed unavailable.")
        except Exception as ex:
             logger.error(f"Failed to mark feed unavailable: {ex}")
    
    # Define Callback for actual Token Invalidation (non-403 auth failures)
    async def invalidate_token():
        logger.error(f"Invalidating Token for user {user.email}")
        
        # 🔒 CRITICAL: Validate WebSocket state before sending
        from starlette.websockets import WebSocketState
        if websocket.client_state != WebSocketState.CONNECTED:
            logger.warning(f"⚠️ Cannot send TOKEN_EXPIRED - WebSocket already closed/closing")
            # Still update DB even if we can't notify frontend
        else:
            try:
                 # Send TOKEN_EXPIRED event to frontend with clear action guidance
                 await websocket.send_text(json.dumps({
                     "type": "TOKEN_EXPIRED",
                     "msg": "Your Upstox session has expired. Please reconnect your broker account.",
                     "action_required": "RECONNECT_BROKER"
                 }))
                 logger.info("✅ Sent TOKEN_EXPIRED event to frontend")
            except Exception as send_err:
                 logger.error(f"Failed to send TOKEN_EXPIRED event: {send_err}")
                 
        # Create a new DB session for the update (always attempt)
        try:
             async with AsyncSessionLocal() as db_session:
                 stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
                 res = await db_session.execute(stmt)
                 acc = res.scalars().first()
                 if acc:
                     # RACE CONDITION PREVENTER:
                     # Only invalidate if the DB token matches the token used by THIS socket.
                     # If user re-connected, DB has NEW token. We shouldn't kill it.
                     db_token = decrypt(acc.access_token) if acc.access_token else None
                     if db_token != access_token:
                         logger.warning("Token mismatch during invalidation. DB has newer token. Skipping invalidation.")
                         return

                     logger.info(f"Marking token EXPIRED for user {user.email}")
                     acc.status = UpstoxStatus.TOKEN_EXPIRED
                     acc.access_token = None
                     acc.token_expiry = None
                     await db_session.commit()
                     logger.info("DB Updated: Token marked EXPIRED")
                 else:
                     logger.warning("No account found to invalidate.")
        except Exception as ex:
             logger.error(f"Failed to invalidate token: {ex}")
    
    # Define callback for successful feed connection
    async def on_feed_connected():
        """Called when Upstox Feed opens successfully"""
        logger.info(f"✅ Feed CONNECTED for user {user.email}")
        
        # 🔒 CRITICAL: Validate WebSocket state before sending
        from starlette.websockets import WebSocketState
        if websocket.client_state != WebSocketState.CONNECTED:
            logger.warning(f"⚠️ Cannot send FEED_CONNECTED - WebSocket already closed/closing")
            return
        
        try:
            # 📌 5️⃣ FRONTEND ↔ BACKEND SIGNALING
            logger.info(f"[ws] Sending UPSTOX_FEED_CONNECTED event to frontend")
            await websocket.send_text(json.dumps({
                "type": "UPSTOX_FEED_CONNECTED",
                "msg": "Market Data Feed ready"
            }))
            
            # 📌 4️⃣ DATABASE STATE TRANSITIONS
            async with AsyncSessionLocal() as db_session:
                logger.info(f"[db] Updating feed_entitlement → 1 (AVAILABLE)")
                stmt = select(UpstoxAccount).filter(UpstoxAccount.user_id == user.id)
                res = await db_session.execute(stmt)
                acc = res.scalars().first()
                if acc:
                    acc.feed_entitlement = 1  # Feed available
                    db_session.add(acc)
                    await db_session.commit()  # CRITICAL: Commit changes
                    logger.info(f"[db] ✅ Feed entitlement persisted successfully")
                    logger.info("DB Updated: Feed marked AVAILABLE")
        except Exception as ex:
            logger.error(f"Failed to mark feed connected: {ex}")

    # 5. RUN LOOP (Outside DB Session Scope)
    # Initialize Bridge with BOTH callbacks
    # 🔴 CRITICAL: Set underlying_key to Nifty 50 for spot price tracking
    bridge = UpstoxFeedBridge(
        websocket, 
        access_token, 
        api_key=api_key,
        underlying_key="NSE_INDEX|Nifty 50",  # Default to Nifty 50 for spot price
        on_token_invalid=invalidate_token,
        on_feed_unavailable=mark_feed_unavailable
    )
    manager.bridges[websocket] = bridge
    
    # Register feed connected callback
    # We'll modify market_feed.py to call this on successful open
    bridge.on_feed_connected_callback = on_feed_connected
    
    bridge_task = asyncio.create_task(bridge.connect_and_run())

    try:
        while True:
            data_str = await websocket.receive_text()
            logger.debug(f"WS Received: {data_str[:100]}") # Log first 100 chars
            try:
                msg = json.loads(data_str)
                action = msg.get("action")
                keys = msg.get("keys", [])
                underlying_key = msg.get("underlying_key")  # NEW: For switch_underlying
                
                if action == "subscribe" and isinstance(keys, list):
                    logger.info(f"📋 Subscribe action for {len(keys)} keys (initial setup)")
                    # Initial subscription before connection
                    await bridge.subscribe(keys)
                
                elif action == "switch_underlying":
                    # 🚨 SESSION-BOUND: Hard switch to new underlying
                    # CRITICAL FIX: Pass the frontend keys to backend!
                    # The backend's switch_underlying() NEEDS these keys to build the subscription list
                    if not underlying_key:
                        logger.error("❌ switch_underlying requires 'underlying_key'")
                    else:
                        logger.info(f"🔄 SWITCH UNDERLYING REQUEST: {bridge.underlying_key} → {underlying_key}")
                        # ✅ FIX: PASS keys to backend (don't ignore them!)
                        # Backend will use these to immediately subscribe to all strikes
                        logger.info(f"   Passing {len(keys)} frontend keys to backend for subscription")
                        
                        try:
                            await bridge.switch_underlying(underlying_key, keys)
                            
                            # ✅ FIX Issue #9: Send Acknowledgment to Frontend
                            # This lets the frontend know the subscription was accepted and is being processed
                            await websocket.send_text(json.dumps({
                                "type": "SUBSCRIPTION_ACK",
                                "status": "success",
                                "underlying": underlying_key,
                                "count": len(keys)
                            }))
                            logger.info(f"✅ Sent SUBSCRIPTION_ACK to frontend for {underlying_key}")
                            
                        except Exception as e:
                            logger.error(f"❌ switch_underlying failed: {e}")
                            await websocket.send_text(json.dumps({
                                "type": "SUBSCRIPTION_ERROR",
                                "error": str(e),
                                "underlying": underlying_key
                            }))
                
                elif action == "change_underlying":
                    # DEPRECATED: Redirect to switch_underlying
                    logger.warning("⚠️ 'change_underlying' is deprecated - use 'switch_underlying'")
                    if underlying_key and keys:
                        await bridge.switch_underlying(underlying_key, set(keys))
                    else:
                        logger.error("❌ Missing underlying_key or keys")
                
                elif action == "unsubscribe":
                    # ❌ NOT SUPPORTED - Ignored per design
                    logger.warning("🚫 Received 'unsubscribe' - NOT SUPPORTED in SESSION-BOUND mode")
                    logger.warning("📋 Request ignored - feed state unchanged")
                    logger.warning("💡 Use 'switch_underlying' to change instruments")
                    # DO NOT call bridge.unsubscribe - it's a NO-OP anyway
                
                else:
                    logger.warning(f"⚠️ Unknown WS action: {action}")
            except json.JSONDecodeError:
                pass
            
    except WebSocketDisconnect:
        await manager.disconnect(websocket, user_email) # user.email might be out of scope?
        # Re-fetch email from active connections? 
        # Actually user.email IS in scope because 'user' was defined in the outer function scope 
        # (Wait, user was defined inside 'async with'. It might be unbound if auth failed, but we return then.)
        # Python variables leak to function scope. But safely...
        # 'user' is defined in the 'try' block. If we are here, auth succeeded.
        pass
    except Exception as e:
        logger.error(f"WS Loop Error: {e}")
        # Need user email to disconnect
        # We can store email in manager.bridges or similar?
        # Or just catch-all disconnect
        await manager.disconnect(websocket, user_email)
    finally:
        bridge_task.cancel()
