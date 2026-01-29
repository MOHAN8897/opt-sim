import asyncio
import json
import logging
import httpx
from datetime import datetime
import threading
import uuid
from decimal import Decimal
from .greeks_calculator import calculate_greeks
from .redis_client import redis_manager
from .instrument_manager import instrument_manager
from .execution_engine import check_pending_orders
from .database import AsyncSessionLocal

# Upstox SDK Imports
try:
    from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
    import upstox_client
except ImportError:
    MarketDataStreamerV3 = None
    upstox_client = None

logger = logging.getLogger("api.feed")

LIVE_STRIKE_WINDOW = 8  # Configurable window size (±8 strikes)

def normalize_instrument_key(key: str) -> str:
    """
    Normalize instrument key format for consistent matching.
    Handles separators, URL encoding, and whitespace.
    
    Examples:
        "NSE_INDEX:Nifty 50" -> "NSE_INDEX|Nifty 50"
        "NSE_INDEX:Nifty%2050" -> "NSE_INDEX|Nifty 50"
        "NSE_INDEX|Nifty 50 " -> "NSE_INDEX|Nifty 50"
    """
    # Replace separator
    normalized = key.replace(":", "|")
    # Handle URL encoding (Upstox might encode spaces)
    normalized = normalized.replace("%20", " ")
    # Trim any extra whitespace around pipe separator
    parts = normalized.split("|")
    if len(parts) == 2:
        exchange, symbol = parts
        normalized = f"{exchange.strip()}|{symbol.strip()}"
    return normalized

class UpstoxAuthWrapper:
    """Wrapper to make string token look like API Client config"""
    def __init__(self, token, api_key=None):
        self.access_token = token
        self.api_key_val = api_key
        
        # Build configuration object similar to SDK
        class Configuration:
            def __init__(self, t, k):
                self.access_token = t
                self.api_key = {"x-api-key": k}
                self.host = "https://api.upstox.com/v2"
            def auth_settings(self):
                return {"OAUTH2": {"value": f"Bearer {self.access_token}"}}
            def get_api_key_with_prefix(self, key):
                return self.api_key.get(key)
        
        self.configuration = Configuration(token, api_key)
        
        # Debug logging (masked)
        masked_token = f"{token[:5]}...{token[-5:]}" if token and len(token) > 10 else "N/A"
        masked_key = f"{api_key[:2]}...{api_key[-2:]}" if api_key and len(api_key) > 4 else "N/A"
        logger.debug(f"UpstoxAuthWrapper initialized. Token: {masked_token}, Key: {masked_key}")

class UpstoxFeedBridge:
    """SESSION-BOUND Upstox Feed: One underlying = One complete feed session"""
    
    # Feed state machine - Backend is ALWAYS the source of truth
    FEED_STATES = {
        "MARKET_CLOSED",      # Market closed, WS not applicable
        "NOT_CONNECTED",      # Market open, not yet connected  
        "CONNECTING",         # Authorization + connection in progress
        "CONNECTED",          # Feed active and receiving ticks
        "FAILED",             # Permanent failure
        "DISCONNECTING"       # Graceful shutdown in progress
    }
    
    def __init__(self, user_ws, access_token: str, api_key: str = None, expiry_date: str = None, underlying_key: str = None, on_token_invalid=None, on_feed_unavailable=None):
        self.user_ws = user_ws
        self.access_token = access_token
        self.api_key = api_key
        self.expiry_date = expiry_date
        self.underlying_key = underlying_key
        self.on_token_invalid = on_token_invalid
        self.on_feed_unavailable = on_feed_unavailable
        self.on_feed_connected_callback = None  # Will be set by socket_manager after init
        
        # SESSION-BOUND: Subscriptions are IMMUTABLE once connected
        self.subscriptions = set()
        self.session_locked = False  # Locked after first successful connect
        
        self.streamer = None
        self.feed_thread = None
        self.keep_running = True
        
        # Feed State Machine - SINGLE SOURCE OF TRUTH
        self.connection_state = "NOT_CONNECTED"
        self.custom_feed = None
        
        # Store event loop for cross-thread callbacks
        self.loop = asyncio.get_event_loop()
        
        # Greeks calculation params
        self.spot_ltp = 0
        self.greeks_cache = {}
        self.greeks_throttle_threshold = 0.5
        
        # Performance: Batching & Throttling
        self.update_buffer = {}  # Store latest updates to send in batch
        self.last_greeks_calc = {} # Key -> Last Calc Timestamp
        self.last_redis_update = {} # Key -> Last Redis Update Timestamp
        self.last_execution_trigger = {} # Key -> Last Execution Trigger Timestamp
        self.last_execution_trigger = {} # Key -> Last Execution Trigger Timestamp
        self.last_execution_trigger = {} # Key -> Last Execution Trigger Timestamp
        self.broadcast_task = None
        self.execution_task = None # ✅ NEW: Background Execution Monitor

        
        # 🟢 PHASE 3: SEQUENCE TRACKING
        self.seq_map = {} # Key -> Sequence Number (int)
        
        # 🟢 PHASE 3: SEQUENCE TRACKING
        self.seq_map = {} # Key -> Sequence Number (int)
        
        self.connect_lock = asyncio.Lock()
        self.sub_lock = asyncio.Lock() # ✅ NEW: Subscription Mutation Lock
        
        # 🟢 PHASE 1: STABILITY & STATE
        self.current_atm = None
        self.reset_in_progress = False
        self.last_reset_ts = 0
        self.strike_step = 50 # Default for Nifty, auto-detect later
        self.instrument_expiry = None # Store expiry for key generation
        
        self.instrument_expiry = None # Store expiry for key generation
        
        # 🟢 METRICS & DIAGNOSTICS (Production Grade)
        self.feed_id = str(uuid.uuid4())[:8]
        self.state_since_ts = datetime.now()
        self.last_reset_reason = None
        self.tick_metrics = {
            "count_1s": 0,
            "count_5s": 0,
            "last_tick_ts": 0,
            "last_broker_ts": 0,
            "max_gap_ms": 0,
            "gap_window_start": 0
        }
        self.dropped_updates_count = 0
        self.metrics_reset_ts = 0
        self.last_feed_state_version = 0  # ✅ Versioning for Feed State
        
        logger.info(f"🔧 UpstoxFeedBridge initialized [ID: {self.feed_id}]")
        logger.info(f"📍 Underlying: {underlying_key or 'will be set on first subscription'}")

    def is_market_open(self) -> bool:
        """Check if market is currently open (NSE timing: Mon-Fri 09:15-15:30 IST)."""
        now = datetime.now()
        
        # Weekend check
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Trading hours check (NSE)
        start_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
        end_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        is_open = start_time <= now <= end_time
        
        if not is_open:
           logger.debug(f"⏰ Market Status: CLOSED (Current: {now.strftime('%H:%M')}, Trading: 09:15-15:30)")
        
        return is_open
    
    def _is_ws_open(self) -> bool:
        """Check if user WebSocket is still open and ready to send messages."""
        try:
            # Use starlette directly as FastAPI re-exports can vary
            from starlette.websockets import WebSocketState
            if hasattr(self.user_ws, 'client_state'):
                return self.user_ws.client_state == WebSocketState.CONNECTED
            return self.user_ws is not None
        except Exception:
            # If import fails or anything else, assume OPEN to avoid false negatives
            # unless we know it's None
            return self.user_ws is not None

    def on_error(self, error):
        # 📌 3️⃣ WEBSOCKET HANDSHAKE & ERROR CLASSIFICATION
        logger.error(f"[feed] WebSocket error received")
        logger.error(f"[feed] Error raw: {error}")
        
        # Check for 403 Forbidden - FEED ENTITLEMENT FAILURE (NOT token expiry)
        # NOTE: We rely on string matching since Upstox SDK doesn't provide structured error codes
        # Future improvement: Check error.code if/when SDK provides it
        err_str = str(error).lower()
        
        if "403" in err_str or "forbidden" in err_str:
             logger.error(f"[feed] Error type=HTTP")
             logger.error(f"[feed] Error code=403")
             logger.error(f"[feed] 🚫 403 Forbidden – Market Data Feed entitlement missing")
             logger.error(f"[feed] Token is valid for REST APIs")
             logger.error(f"[feed] User action required: Enable Market Data Feed & regenerate token")
             
             # DO NOT invalidate token - it's valid for REST
             # Instead, mark feed as unavailable
             if self.on_feed_unavailable:
                 asyncio.run_coroutine_threadsafe(self.on_feed_unavailable(), self.loop)
             return
        
        elif "401" in err_str or "unauthorized" in err_str:
            logger.error(f"[feed] Error type=HTTP")
            logger.error(f"[feed] Error code=401")
            logger.error(f"[feed] Token is invalid or expired")
            if self.on_token_invalid:
                asyncio.run_coroutine_threadsafe(self.on_token_invalid(), self.loop)
            return
        
        elif "timeout" in err_str:
            logger.error(f"[feed] Error type=NETWORK")
            logger.error(f"[feed] Error code=timeout")
        
        else:
            logger.error(f"[feed] Error type=UNKNOWN")
             
        # For other errors (network, etc), log but let SDK handle auto-reconnect
        logger.warning(f"[feed] Non-critical error - SDK will auto-reconnect if configured.")

    async def authorize_websocket(self) -> bool:
        """
        Call Upstox WebSocket authorization endpoint to verify access.
        
        This is CRITICAL for Market Data Feed V3:
        - REST APIs use simple Bearer token
        - WebSocket requires calling /authorize endpoint first
        - This endpoint verifies feed entitlement and returns authorized URL
        
        Returns:
            bool: True if authorization successful, False otherwise
        """
        try:
            logger.info("🔐 Calling WebSocket authorization endpoint...")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.upstox.com/v3/feed/market-data-feed/authorize",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        # Note: The SDK should internally use this authorization
                        # We just need to verify it works before connecting
                        logger.info("✅ WebSocket authorization successful!")
                        logger.debug(f"Got authorized URL (length: {len(data.get('data',{}).get('authorized_redirect_uri',''))})")
                        return True
                    else:
                        logger.error(f"❌ Authorization response status: {data.get('status')}")
                        return False
                        
                elif response.status_code == 403:
                    logger.error("❌ 403 Forbidden on authorization endpoint")
                    logger.error("This means your access token lacks Market Data Feed permission")
                    logger.error("Check Upstox Developer Console:")
                    logger.error("  1. Go to your app settings")
                    logger.error("  2. Enable 'Market Data Feed' API")
                    logger.error("  3. Regenerate access token AFTER enabling")
                    return False
                    
                elif response.status_code == 401:
                    logger.error("❌ 401 Unauthorized - access token is invalid or expired")
                    # Trigger token invalidation callback
                    if self.on_token_invalid:
                        logger.info("Triggering on_token_invalid callback")
                        asyncio.run_coroutine_threadsafe(self.on_token_invalid(), self.loop)
                    return False
                    
                else:
                    logger.error(f"❌ Authorization failed with status {response.status_code}")
                    logger.error(f"Response: {response.text[:200]}")
                    return False
                    
        except httpx.TimeoutException:
            logger.error("❌ Authorization endpoint timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Authorization endpoint error: {e}")
            return False

    async def connect_and_run(self):
        """
        SESSION-BOUND connection: Market closed = REST only, Market open = WS feed.
        
        🚨 CRITICAL RULES:
        1. Market CLOSED → Skip WS, send MARKET_CLOSED event
        2. Market OPEN → Connect WS with current subscriptions
        3. Once connected → Session LOCKED (no modifications)
        """
        async with self.connect_lock:
            # 🔒 LOCK ACQUIRED: Protect State Transitions
            async with self.sub_lock:
                if self.connection_state in ["CONNECTED", "CONNECTING"]:
                    logger.warning(f"⚠️ Feed already {self.connection_state} – skipping duplicate connect")
                    return
            
                # ====================================================================
                # RULE #2: MARKET CLOSED MODE = REST ONLY
                # ====================================================================
                if not self.is_market_open():
                    logger.warning("⛔ Market is CLOSED – Entering REST-ONLY mode")
                    logger.warning("❌ WebSocket will NOT be connected")
                    
                    self.connection_state = "MARKET_CLOSED"
                    
                    # Notify frontend: Market closed, use REST only
                    await self._send_market_closed_event()
                    return  # DO NOT proceed with WebSocket connection
                
                # Market is OPEN - proceed with WebSocket
                self.connection_state = "CONNECTING"
                self.spot_ltp = 0.0
                logger.info("🟢 Market is OPEN – Proceeding with WebSocket connection")
                logger.info(f"[feed] Connection state: NOT_CONNECTED → CONNECTING")

            # 🛑 RACE CONDITION FIX (Issue #4): 
            # Ensure any previous custom_feed is fully cleaned up before creating a new one.
            if self.custom_feed:
                logger.warning("⚠️ Found existing custom_feed during connect_and_run. Forcing cleanup.")
                try:
                    await self.custom_feed.disconnect()
                except: pass
                self.custom_feed = None

            # ✅ FIX: Resurrection - Ensure loop flag is True
            self.keep_running = True
            
            # Wait for instruments to load
            from .instrument_manager import instrument_manager
            wait_count = 0
            while not instrument_manager.is_loaded and wait_count < 30:
                logger.info("[feed] Waiting for Instrument Manager to load...")
                await asyncio.sleep(1.0)
                wait_count += 1
            
            # This code is now handled above - removed redundant check

            try:
                from .upstox_websocket_v3 import UpstoxWebSocketFeed
            except ImportError:
                logger.error("Custom WebSocket module not found")
                await self.user_ws.send_text(json.dumps({"type": "ERROR", "msg": "Backend module missing"}))
                self.connection_state = "FAILED"
                return
                
            # 📌 2️⃣ WEBSOCKET INITIALIZATION FLOW
            logger.info(f"[feed] Attempting Market Feed connection")
            logger.info(f"[feed] Underlying={self.underlying_key or 'dynamic mode'}")
            
            # CRITICAL STEP: Authorize WebSocket is handled inside UpstoxWebSocketFeed
            # We skip the redundant check here to avoid 403s from double-invocation
            # logger.info("Step 1/2: Authorizing WebSocket (Delegated to Custom Feed)...")
            
            pass

            # 2. Load default Nifty 50 instruments if no subscriptions yet
            if not self.subscriptions or len(self.subscriptions) == 0:
                logger.info("📋 Loading default Nifty 50 subscription...")
                default_instruments = await self._get_default_nifty_instruments()
                if default_instruments:
                    self.subscriptions.update(default_instruments)
                    logger.info(f"✅ Loaded {len(default_instruments)} default Nifty instruments")
                else:
                    logger.warning("⚠️ Could not load default instruments - WebSocket will wait for manual subscription")
                    # Allow empty connect? Upstox says NO (see Issue 6).
                    # But we can connect and subscribe later via restart.
                    # Upstox V3 requires instruments at connect time usually?
                    # The Custom Feed checks for empty instruments.
                    pass

            # 3. Setup and connect custom WebSocket
            logger.info("Step 2/2: Connecting to authorized WebSocket with protobuf support...")
            
            # Create custom WebSocket feed
            self.custom_feed = UpstoxWebSocketFeed(
                access_token=self.access_token,
                instrument_keys=self.subscriptions,
                on_message=self._on_custom_message,
                on_open=self._on_custom_open,
                on_error=self._on_custom_error,
                on_close=self._on_custom_close,
            )
            
            # Connect (this is async and will run until disconnected)
            # We must run this as a task so we don't block `connect_and_run` caller?
            # `connect_and_run` IS the task usually. 
            # If we await custom_feed.connect(), we block here. Correct.
            try:
                await self.custom_feed.connect()
            except Exception as e:
                logger.error(f"Custom feed connection error: {e}")
                self.connection_state = "FAILED"
                if self.on_feed_unavailable:
                    await self.on_feed_unavailable()
    
    async def restart_feed(self, new_keys: set = None):
        """
        Restart the feed securely: Stop -> Authorize -> Connect.
        Required for Upstox V3 when changing subscriptions.
        """
        logger.info("🔄 Restarting Market Data Feed (Stop -> Auth -> Connect)...")
        
        # 1. Update subscriptions
        # 1. Update subscriptions
        async with self.sub_lock:
             if new_keys:
                 self.subscriptions.update(new_keys)
        
        # 2. Stop existing
        await self.stop(restart=True)
        
        # 3. Connect again (which includes Auth)
        # We need to run this separate from the current task if we are inside a callback?
        # Usually restart is called from subscribe() which might be from REST API handler.
        # So we can just await connect_and_run()
        
        # Wait a bit for cleanup (increased to avoid rate limits/race conditions)
        logger.info("[feed] Restart sleeping for 2.0s...")
        await asyncio.sleep(2.0)
        logger.info("[feed] Restart awake. Triggering connect_and_run.")
        
        # Re-trigger connection
        # Since connect_and_run blocks, we should spawn it?
        # Or if we are the main loop runner?
        asyncio.create_task(self.connect_and_run())

    async def _get_default_nifty_instruments(self) -> set:
        """
        Get default Nifty 50 instruments for subscription.
        Returns Nifty 50 index + nearby ATM options.
        """
        try:
            # Get Nifty 50 spot
            nifty_spot_key = "NSE_INDEX|Nifty 50"
            instruments = {nifty_spot_key}
            
            # Get nearest expiry
            from .instrument_manager import instrument_manager
            expiry_dates = instrument_manager.get_expiry_dates(nifty_spot_key)
            
            if not expiry_dates:
                logger.warning("No expiry dates found for Nifty 50")
                return instruments
            
            nearest_expiry = expiry_dates[0]
            
            # Get Nifty LTP for ATM strike calculation
            async with httpx.AsyncClient(timeout=10.0) as client:
                ltp_response = await client.get(
                    f"https://api.upstox.com/v2/market-quote/ltp?instrument_key={nifty_spot_key}",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                )
                
                if ltp_response.status_code == 200:
                    data = ltp_response.json()
                    # ✅ FIX: Handle both separators
                    formatted_key = nifty_spot_key.replace("|", ":")
                    item_data = data.get("data", {}).get(nifty_spot_key, {}) or data.get("data", {}).get(formatted_key, {})
                    nifty_ltp = item_data.get("last_price", 23500)
                elif ltp_response.status_code == 401:
                    logger.error("❌ 401 Unauthorized in default instruments fetch - Token expired")
                    if self.on_token_invalid:
                        asyncio.run_coroutine_threadsafe(self.on_token_invalid(), self.loop)
                    return set()  # Return empty set to abort connection
                else:
                    nifty_ltp = 23500  # Fallback
            
            # Round to nearest 50 for ATM
            atm_strike = round(nifty_ltp / 50) * 50
            
            # Get option chain around ATM (±LIVE_STRIKE_WINDOW strikes)
            chain = instrument_manager.get_option_chain(nifty_spot_key, nearest_expiry, atm_strike, count=LIVE_STRIKE_WINDOW)
            
            for row in chain:
                ce = row.get("call_options", {})
                pe = row.get("put_options", {})
                
                if ce.get("instrument_key"):
                    instruments.add(ce["instrument_key"])
                if pe.get("instrument_key"):
                    instruments.add(pe["instrument_key"])
            
            logger.info(f"Default Nifty setup: Expiry={nearest_expiry}, ATM={atm_strike}, Total instruments={len(instruments)}")
            return instruments
            
        except Exception as e:
            logger.error(f"Failed to get default Nifty instruments: {e}")
            return set()
    
    # Custom WebSocket callback handlers
    def _on_custom_open(self):
        """Called when custom WebSocket opens"""
        # 📌 3️⃣ WEBSOCKET HANDSHAKE SUCCESS
        self.connection_state = "CONNECTED"
        logger.info(f"[feed] Connection state: CONNECTING → CONNECTED")
        logger.info(f"[feed] WebSocket handshake successful")
        logger.info(f"[feed] Upstox feed connected (market may be closed)")
        
        # 🚀 START BROADCAST LOOP - ONLY AFTER CONNECTION IS CONFIRMED
        # This prevents race condition where loop tries to send before connection is ready
        if not self.broadcast_task or self.broadcast_task.done():
            logger.info("🚀 Starting broadcast loop to send updates to frontend")
            self.broadcast_task = asyncio.run_coroutine_threadsafe(
                self._broadcast_loop(), 
                self.loop
            )

        # 🚀 START EXECUTION MONITOR - Runs execution logic periodically (1s) instead of per-tick
        if not self.execution_task or self.execution_task.done():
            logger.info("🚀 Starting execution monitor loop")
            self.execution_task = asyncio.run_coroutine_threadsafe(
                self._execution_monitor_loop(),
                self.loop
            )

        
        # Notify socket_manager that feed is ready
        if self.on_feed_connected_callback:
            asyncio.run_coroutine_threadsafe(self.on_feed_connected_callback(), self.loop)

        # 4. Broadcast Initial Feed State (Guaranteed Delivery)
        # Using run_coroutine_threadsafe because we're in a synchronous callback
        asyncio.run_coroutine_threadsafe(
            self._broadcast_feed_state(
                "LIVE", 
                self.current_atm or 0, 
                self.build_live_strikes(self.current_atm or 0, self.strike_step, LIVE_STRIKE_WINDOW) if self.current_atm else [],
                reason="CONNECTED"
            ),
            self.loop
        )
    
    
    def _on_custom_message(self, decoded_data: dict):
        """Called when custom WebSocket receives decoded protobuf message"""
        # 🔍 DEBUG: Log message reception
        if decoded_data:
            num_feeds = len(decoded_data) if not isinstance(decoded_data, dict) or "feeds" not in decoded_data else len(decoded_data.get("feeds", {}))
            if num_feeds > 0:
                logger.info(f"📥 Received WebSocket data: {num_feeds} instruments")
        
        if self.keep_running:
            asyncio.run_coroutine_threadsafe(self._process_data(decoded_data), self.loop)
    
    def _on_custom_error(self, error):
        """Called when custom WebSocket encounters error"""
        logger.error(f"Custom WebSocket error: {error}")
        # Don't call on_feed_unavailable for transient errors
        # Only for permanent failures
    
    def _on_custom_close(self):
        """Called when custom WebSocket closes"""
        self.connection_state = "NOT_CONNECTED"
        logger.warning("Custom WebSocket closed")
        logger.info(f"[feed] Connection state: CONNECTED/FAILED → NOT_CONNECTED")


    def on_open(self, *args):
        logger.info("✅ Upstox WebSocket Connected (via SDK).")
        # Notify frontend that feed is ready
        if self.on_feed_connected_callback:
            asyncio.run_coroutine_threadsafe(self.on_feed_connected_callback(), self.loop)
        
        # Re-subscribe if needed, though SDK handles initial keys
        if self.subscriptions:
            logger.info(f"on_open: Resubscribing to {len(self.subscriptions)} keys")
            self.streamer.subscribe(list(self.subscriptions), "full")

    def on_message(self, message):
        """Callback from SDK Thread - must be thread-safe"""
        # message is a DICT (JSON) already decoded by SDK
        # We need to process it and send to user_ws (async)
        
        # Scheduling the async processing to the main loop
        # Scheduling the async processing to the main loop
        if self.keep_running:
            # logger.debug("on_message: Received data from SDK")
            asyncio.run_coroutine_threadsafe(self._process_data(message), self.loop)


    def on_close(self, *args):
        logger.warning("Upstox Streamer Closed.")

    async def _broadcast_loop(self):
        """
        Consumer loop that batches and sends updates to the frontend.
        Running at 20 FPS (0.05s) for near real-time market data.
        """
        logger.info("🎬 Broadcast loop STARTED")
        loop_count = 0
        
        while self.keep_running:
            try:
                await asyncio.sleep(0.05)  # 50ms = 20 FPS (was 200ms = 5 FPS)
                loop_count += 1
                
                # Log every 100 iterations (5 seconds) to show loop is alive
                # Log every 100 iterations (5 seconds) to show loop is alive
                # Log every 100 iterations (5 seconds) to show loop is alive
                if loop_count % 100 == 0:
                    logger.info(f"🔄 Broadcast loop alive (iteration {loop_count}, buffer size: {len(self.update_buffer)})")

                    # ✅ FIX Issue #6: Subscription Health Check
                    # Log warning if we have active subscriptions but no data in buffer for a long time
                    if len(self.subscriptions) > 0 and len(self.update_buffer) == 0 and loop_count > 200:
                         logger.warning(f"⚠️ STARVATION WARNING: {len(self.subscriptions)} keys subscribed but ZERO updates in buffer.")
                         
                    # Log active keys count vs expected
                    if len(self.subscriptions) < 5 and self.connection_state == "CONNECTED":
                         logger.warning(f"⚠️ LOW SUBSCRIPTION COUNT: Only {len(self.subscriptions)} keys. Expected 20+")

                # 🟢 PHASE 3: FEED HEALTH HEARTBEAT (1/sec = 20 iterations)
                if loop_count % 20 == 0 and self._is_ws_open():
                    # Determine Status
                    feed_status = "RESETTING" if self.reset_in_progress else "LIVE"
                    
                    # Gap 2: Explicit active_keys: 0 during RESETTING
                    reported_active_keys = 0 if self.reset_in_progress else len(self.subscriptions)

                    # 🟡 INVARIANT ASSERTION (User Rule 2)
                    if feed_status == "LIVE":
                        expected_min = 25 
                        if reported_active_keys < expected_min:
                            if loop_count % 100 == 0: 
                                logger.warning(f"⚠️ Feed Health: Low active keys ({reported_active_keys}/{expected_min}). Keeping connection alive.")

                    # ✅ FIX #1: SYNTHETIC SPOT INJECTION (Option B)
                    # If Spot is missing/stale, derive it from Options (Put - Call + Strike = Spot approx)
                    # This ensures Frontend ALWAYS has a spot price to anchor the chain.
                    if self.underlying_key and (self.spot_ltp == 0 or (datetime.now().timestamp() - self.tick_metrics["last_tick_ts"] > 2.0)):
                         try:
                             # 1. Collect Valid Pairs from Buffer or existing sequence map tracking?
                             # Accessing redis/memory is expensive? No, lets use update_buffer + simple cache check
                             # Just checking the current batch is not enough, as options might not tick this exact frame.
                             # But we need *some* spot.
                             
                             # Let's fallback to REST fetch if truly desperate, BUT Synthetic is faster.
                             # Simplified Synthetic: Iterate REDIS Keys? No (Slow).
                             # Iterate current batch? 
                             pass # Ideally we implement this more robustly below
                         except: pass

                    health_msg = {
                        "type": "FEED_HEALTH",
                        "data": {
                            "state": feed_status,
                            "active_keys": reported_active_keys,
                            "buffer_size": len(self.update_buffer),
                            "reset_locked": self.reset_in_progress,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                    try:
                        await self.user_ws.send_text(json.dumps(health_msg))
                    except: pass 
                
                # Check for pending updates in buffer
                if self.update_buffer:
                    # Atomic-like swap to clear buffer while processing
                    updates_to_send = self.update_buffer
                    self.update_buffer = {}
                    
                    # 🔴 CRITICAL FIX: ALWAYS INJECT SPOT PRICE IF WE HAVE IT
                    # The underlying index may not always appear in the buffer due to:
                    #   - Upstox sending it less frequently than options
                    #   - Subscription mode filtering
                    #   - Network timing
                    # Therefore, we FORCE inject the last known spot on EVERY broadcast
                    if self.underlying_key and self.spot_ltp > 0:
                        # Always include real spot if we have it, even if not in buffer
                        updates_to_send[self.underlying_key] = {
                            "ltp": str(self.spot_ltp),
                            "volume": 0,
                            "seq": self.seq_map.get(self.underlying_key, 0),
                            "recv_ts": int(datetime.now().timestamp() * 1000),
                            "synthetic": False
                        }
                        logger.debug(f"✅ Injected Real Spot: {self.underlying_key} = {self.spot_ltp}")
                    
                    # ✅ FIX #1: FORCE SYNTHETIC SPOT IF MISSING
                    # If underlying_key is NOT in updates AND we don't have real spot, derive it
                    elif self.underlying_key and self.underlying_key not in updates_to_send:
                         # Pure synthetic fallback (no real spot available)
                         # Try to derive from options in THIS batch
                         if len(updates_to_send) >= 2:
                             # Scan for any CE/PE pair at same strike to estimate spot
                             # Spot ≈ Strike + Call - Put (Put-Call Parity: C - P = S - K*e^-rt) -> S = C - P + K (ignoring interest/div)
                             try:
                                 # Group by strike using InstrumentManager (Robust Lookup)
                                 # This fixes the issue where regex failed on opaque tokens (NSE_FO|12345)
                                 from .instrument_manager import instrument_manager
                                 
                                 strikes_data = {}
                                 
                                 for k, v in updates_to_send.items():
                                     # Resolving token to details
                                     details = instrument_manager.get_instrument_details(k)
                                     
                                     if details:
                                         strike = float(details.get("strike", 0))
                                         type_ = details.get("option_type") # CE or PE
                                         
                                         if strike > 0 and type_ in ["CE", "PE"]:
                                             if strike not in strikes_data: strikes_data[strike] = {}
                                             strikes_data[strike][type_] = float(v.get("ltp", 0))
                                 
                                 # Find first valid pair
                                 for strike, prices in strikes_data.items():
                                     if "CE" in prices and "PE" in prices:
                                         c = prices["CE"]
                                         p = prices["PE"]
                                         if c > 0 and p > 0:
                                             syn_spot = c - p + strike
                                             self.spot_ltp = syn_spot # Cache it
                                             updates_to_send[self.underlying_key] = {
                                                 "ltp": str(syn_spot),
                                                 "volume": 0,
                                                 "seq": 0,
                                                 "recv_ts": int(datetime.now().timestamp() * 1000),
                                                 "synthetic": True,
                                                 "source": "derived"
                                             }
                                             logger.info(f"🧪 Synthetic Spot Derived: {syn_spot:.2f} (from {strike} C:{c} P:{p})")
                                             break
                             except Exception as e:
                                 logger.error(f"Synthetic calc failed: {e}", exc_info=True)
                                 pass

                    if updates_to_send:
                         # 🔒 CRITICAL: Check WebSocket state before sending
                         if not self._is_ws_open():
                             logger.warning(f"⚠️ WebSocket closed - discarding {len(updates_to_send)} buffered updates")
                             break  
                         
                         # 🔍 DEBUG: Log which instruments are being broadcast
                         sample_keys = list(updates_to_send.keys())[:3]
                         # Log batch composition
                         logger.info(f"📤 Broadcasting {len(updates_to_send)} instruments. Keys: {list(updates_to_send.keys())}")
                         
                         # Send batched update
                         msg = {"type": "MARKET_UPDATE", "data": updates_to_send}
                         try:
                             logger.info(f"📤 Sending MARKET_UPDATE to frontend: {len(updates_to_send)} instruments")
                             # Log if index is present
                             if self.underlying_key in updates_to_send:
                                  index_ltp = updates_to_send[self.underlying_key].get('ltp')
                                  logger.info(f"   ✅ INDEX PRESENT: {self.underlying_key} = {index_ltp}")
                             else:
                                  logger.warning(f"   ❌ INDEX MISSING in batch! Keys present: {list(updates_to_send.keys())}")

                             await self.user_ws.send_text(json.dumps(msg))
                         except Exception as e:
                             logger.error(f"Failed to send batched WS message: {e}")
                             if "close" in str(e).lower() or "websocket" in str(e).lower():
                                 logger.error("WebSocket appears closed - stopping broadcast loop")
                                 break 
                             
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
                await asyncio.sleep(1) # Backoff on error

    async def _execution_monitor_loop(self):
        """
        Background task to trigger execution engine for active instruments.
        Replaces the "per-tick" DB trigger to prevent connection starvation.
        Runs every 1.0 second.
        """
        logger.info("⚖️ Execution Monitor loop STARTED")
        from .database import AsyncSessionLocal
        from .models import Order, OrderStatus
        from sqlalchemy import select

        while self.keep_running:
            try:
                await asyncio.sleep(1.0) # 1Hz Polling (User requested 500-1000ms)
                
                # OPTIMIZATION: Query distinct instruments with OPEN/PARTIAL orders directly
                # This prevents spawning DB tasks for instruments with no orders.
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(Order.instrument_key)
                        .filter(Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]))
                        .distinct()
                    )
                    active_keys = result.scalars().all()
                
                if active_keys:
                    # logger.debug(f"⚖️ Found active orders for {len(active_keys)} instruments")
                    for key in active_keys:
                        # Only trigger if we have market data for it (or it's underlying)
                        # We use _trigger_pending_orders but we must ensure it doesn't spam logs
                        asyncio.create_task(self._trigger_pending_orders(key))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in execution monitor loop: {e}")
                await asyncio.sleep(5)


    # 🟢 PHASE 1: CORE HELPERS
    def calculate_atm(self, spot_price: float) -> float:
        """
        Central Source of Truth for ATM Logic.
        Uses Standard Rounding (Half up) to ensure deterministic ATM selection.
        Example: 23525 -> 23550, 23524 -> 23500 (assuming step 50)
        """
        if self.strike_step <= 0: return spot_price
        
        # Standard div/round method
        steps = spot_price / self.strike_step
        return round(steps) * self.strike_step

    def build_live_strikes(self, atm: float, step: float, window: int = LIVE_STRIKE_WINDOW) -> list:
        """Generates STRICT ±window strike list"""
        return [int(atm + i * step) for i in range(-window, window + 1)]

    async def _reset_feed_for_new_atm(self, new_atm: float):
        """
        Phase 1: Dynamic Hard Reset
        Disconnects, rebuilds keys, reconnects.
        Protected by Timeout Failsafe.
        """
        logger.warning(f"[RESET][START] reason=ATM_SHIFT new_atm={new_atm}")
        self.last_reset_reason = "ATM_SHIFT"
        start_time = datetime.now()
        
        try:
            # 1. Update State
            self.current_atm = new_atm
            
            # 🚀 IMMEDIATE NOTIFICATION: Tell frontend we are resetting
            # This allows UI to show "Resubscribing..." or Skeleton State instantly
            await self._broadcast_feed_state("RESETTING", new_atm, [])
            
            # 2. Build New Keys logic ... (preserved from previous step, but re-asserting for context)
            from .instrument_manager import instrument_manager
            
            if not self.instrument_expiry:
                expiry_dates = instrument_manager.get_expiry_dates(self.underlying_key)
                if expiry_dates:
                     self.instrument_expiry = expiry_dates[0]
            
            if not self.instrument_expiry:
                logger.error("[RESET][FAIL] No expiry found")
                return 

            strikes = self.build_live_strikes(new_atm, self.strike_step, LIVE_STRIKE_WINDOW)
            new_keys = set()
            new_keys.add(self.underlying_key)
            
            chain_rows = instrument_manager.get_option_chain(
                self.underlying_key, 
                self.instrument_expiry, 
                new_atm, 
                count=LIVE_STRIKE_WINDOW 
            )
            
            for row in chain_rows:
                if row['call_options'].get('instrument_key'):
                    new_keys.add(row['call_options']['instrument_key'])
                if row['put_options'].get('instrument_key'):
                    new_keys.add(row['put_options']['instrument_key'])

            logger.info(f"[SUBSCRIPTION][BUILD] atm={new_atm} window=±7 count={len(new_keys)}")
            
            # 🏁 TIMEOUT FAILSAFE WRAPPER
            async def _do_reset():
                # 3. Disconnect
                await self.stop(restart=True)
                self.subscriptions = new_keys
                # 4. Reconnect
                await self.connect_and_run()
            
            RESET_TIMEOUT = 10 # seconds
            await asyncio.wait_for(_do_reset(), timeout=RESET_TIMEOUT)
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"[RESET][COMPLETE] atm={new_atm} subscriptions={len(new_keys)} duration={duration:.0f}ms")
            
            # 🟢 PHASE 3: AUDIT LOG
            logger.info(f"[SUBSCRIPTION][FINAL_KEYS] count={len(new_keys)}")
            logger.info(f"   keys={list(new_keys)}")

            # 5. Broadcast Feed State (Explicit Phase LIVE)
            await self._broadcast_feed_state("LIVE", new_atm, strikes)

        except asyncio.TimeoutError:
            logger.error("[RESET][TIMEOUT] Feed stuck resetting. Init Force Restart.")
            self.last_reset_reason = "RESET_TIMEOUT"
            # Gap 3: UI Feedback for Timeout
            await self._broadcast_feed_state("CLOSED", self.current_atm, [], reason="RESET_TIMEOUT")
            await self.force_full_restart()

        except Exception as e:
            logger.error(f"[RESET][ERROR] {e}", exc_info=True)
            asyncio.create_task(self.connect_and_run())

        finally:
             # ✅ CRITICAL: RELEASE LOCK
             self.reset_in_progress = False

    async def force_full_restart(self):
        """Last resort recovery"""
        logger.critical("💀 FORCE FULL RESTART TRIGGERED")
        self.connection_state = "FAILED"
        self.keep_running = False
        await asyncio.sleep(1)
        self.keep_running = True
        self.connection_state = "NOT_CONNECTED"
        asyncio.create_task(self.connect_and_run())

    async def _broadcast_feed_state(self, status: str, atm: float, strikes: list, reason: str = None):
        """Phase 1: Explicit Contract with Versioning"""
        if status != "RESETTING" and status != "CLOSED":
             self.state_since_ts = datetime.now()

        # Increment version (monotonic counter)
        self.last_feed_state_version += 1

        data = {
            "version": self.last_feed_state_version, # ✅ Versioning
            "status": status,
            "current_atm": atm,
            "live_strikes": strikes,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        if reason:
             data["reason"] = reason

        msg = {
            "type": "FEED_STATE",
            "data": data
        }
        if self._is_ws_open():
             await self.user_ws.send_text(json.dumps(msg))
             logger.info(f"📢 FEED_STATE v{self.last_feed_state_version}: {status} (Reason={reason or 'None'})")

    async def _process_data(self, parsed_data):
        """
        Simplified Producer logic:
        1. Extract data (Handles both Custom V3 Simplified and Legacy SDK formats)
        2. Offload Greeks if needed (non-blocking)
        3. Push to buffer
        """
        try:
            if not parsed_data:
                return

            # Detect format: Legacy SDK wraps in "feeds", Custom V3 sends direct dict
            if "feeds" in parsed_data:
                feeds = parsed_data.get("feeds", {})
            else:
                feeds = parsed_data # It IS the feeds items dict
                
            if not feeds:
                return
            
            if not feeds:
                return
            
            # Metrics: Tick Counting
            now_ts = datetime.now().timestamp()
            self.tick_metrics["last_tick_ts"] = now_ts
            self.tick_metrics["count_1s"] += len(feeds) # Count updates, not just messages? Yes.
            
            # Rolling window reset for "Last 1s" (Approximate)
            if now_ts - self.metrics_reset_ts > 1.0:
                 # Move 1s to 5s buffer (decaying average or simple bucket shift?)
                 # For simplicity, just reset 1s count every second, and keep a cumulative for 5s?
                 # Let's keep it simple: Real-time update in debug endpoint can handle "ticks since X"
                 # Ideally we use a deque for exact window, but counter reset is cheaper.
                 # Let's just track cumulative and Reset.
                 self.metrics_reset_ts = now_ts
                 self.tick_metrics["count_5s"] = (self.tick_metrics["count_5s"] or 0) * 0.8 + self.tick_metrics["count_1s"]
                 self.tick_metrics["count_1s"] = 0

            current_time = datetime.now()
            
            for raw_key, feed_data in feeds.items():
                # ✅ FIX: Normalize Key (Upstox sends 'NSE_INDEX:Nifty 50', we want 'NSE_INDEX|Nifty 50')
                key = normalize_instrument_key(raw_key)
                
                ltp = 0.0
                volume = 0
                oi = 0
                
                # --- FORMAT 1: Simplified Custom V3 (Direct keys) ---
                if "ltp" in feed_data:
                    ltp = float(feed_data.get("ltp", 0))
                    volume = int(feed_data.get("volume", 0))
                    oi = int(feed_data.get("oi", 0))
                    
                    # Extract Brokers Greeks if available
                    broker_iv = float(feed_data.get("iv", 0))
                    broker_delta = float(feed_data.get("delta", 0))
                    broker_theta = float(feed_data.get("theta", 0))
                    broker_gamma = float(feed_data.get("gamma", 0))
                    broker_vega = float(feed_data.get("vega", 0))
                    
                    # ✅ Consume Pre-calculated Bid/Ask from Custom Parser
                    bid = float(feed_data.get("bid", 0))
                    ask = float(feed_data.get("ask", 0))
                    bid_qty = int(feed_data.get("bid_qty", 0))
                    ask_qty = int(feed_data.get("ask_qty", 0))

                # --- FORMAT 2: Legacy SDK (Nested Protobuf structure) ---
                else:
                    # Handle FULL mode structure
                    ff = feed_data.get("fullFeed", {})
                    mff = ff.get("marketFF") or ff.get("indexFF", {})
                    
                    # Extract LTP from nested structure
                    ltpc = mff.get("ltpc", {})
                    ltp = float(ltpc.get("ltp", 0))
                    
                    if ltp == 0 and "ltpc" in feed_data:
                        ltp = float(feed_data["ltpc"].get("ltp", 0))

                    volume = int(mff.get("vtt", 0))
                    oi = int(mff.get("oi", 0))
                    
                    broker_iv = float(mff.get("iv", 0))
                    broker_delta = 0
                    if "optionGreeks" in mff:
                        broker_delta = float(mff["optionGreeks"].get("delta", 0))
                        broker_theta = float(mff["optionGreeks"].get("theta", 0))
                        broker_gamma = float(mff["optionGreeks"].get("gamma", 0))
                        broker_vega = float(mff["optionGreeks"].get("vega", 0))
                    
                    # ✅ PHASE 1: Extract Best Bid/Ask from MarketLevel (SAFE VERSION)
                    # WHY: Enables real bid-ask spread in execution engine
                    # CRITICAL FIX #1: Use min/max instead of [0] indexing to handle unsorted depth
                    bid = 0.0
                    ask = 0.0
                    bid_qty = 0
                    ask_qty = 0
                    
                    market_level = mff.get("marketLevel", {})
                    bid_ask_quotes = market_level.get("bidAskQuote", [])
                    
                    if bid_ask_quotes and len(bid_ask_quotes) > 0:
                        # ✅ CRITICAL FIX: Use min/max instead of assuming [0] is best
                        # WHY: Broker may send unsorted depth during:
                        #   - Reconnects
                        #   - Partial updates  
                        #   - Illiquid strikes
                        # Using index [0] can cause crossed markets
                        
                        all_bids = [float(q.get("bidP", 0)) for q in bid_ask_quotes if q.get("bidP", 0) > 0]
                        all_asks = [float(q.get("askP", 0)) for q in bid_ask_quotes if q.get("askP", 0) > 0]
                        
                        if all_bids:
                            bid = max(all_bids)  # Highest bid = best bid
                            # Find quantity for this bid
                            for q in bid_ask_quotes:
                                if float(q.get("bidP", 0)) == bid:
                                    bid_qty = int(q.get("bidQ", 0))
                                    break
                        
                        if all_asks:
                            ask = min(all_asks)  # Lowest ask = best ask
                            # Find quantity for this ask
                            for q in bid_ask_quotes:
                                if float(q.get("askP", 0)) == ask:
                                    ask_qty = int(q.get("askQ", 0))
                                    break
                        
                        # Log successful extraction (helps debug subscription mode)
                        if bid > 0 and ask > 0:
                            logger.debug(f"[BID/ASK] {key}: Bid={bid}x{bid_qty} Ask={ask}x{ask_qty} (from {len(bid_ask_quotes)} levels)")
                    else:
                        # Normal for: LTPC mode, indices, market closed
                        logger.debug(f"[BID/ASK] {key}: No market depth available")


                if ltp == 0: continue

                # 🟢 PHASE 1: DYNAMIC RESET MONITOR
                if key == self.underlying_key:
                    self.spot_ltp = ltp
                    # ✅ DEBUG: Explicitly log Index ticks (often missed)
                    # logger.info(f"🎯 Spot Price Updated: {key} = ₹{ltp:.2f}")

                    
                    # Check ATM Shift
                    new_atm = self.calculate_atm(ltp)
                    
                    # Initialize ATM if Null (First Tick)
                    if self.current_atm is None:
                        logger.info(f"🎯 FIRST SPOT TICK DETECTED for {key}. Ltp={ltp}, NewATM={new_atm}")
                        if not self.reset_in_progress:
                             # FIX #2 & #3: Only reset if keys are minimal (spot-only)
                             # If frontend keys already subscribed, skip this reset
                             if len(self.subscriptions) <= 2:
                                 logger.info(f"[ATM][INIT] First Tick. Setting ATM={new_atm}, triggering reset for option keys")
                                 self.current_atm = new_atm
                                 self.reset_in_progress = True
                                 asyncio.create_task(self._reset_feed_for_new_atm(new_atm))
                             else:
                                 logger.info(f"✅ [FIX#2] Frontend keys already active, skipping unnecessary reset. ATM={new_atm}")
                                 self.current_atm = new_atm
                    
                    elif new_atm != self.current_atm:
                         # FIX #3: Add Hysteresis to ATM Reset (FIXES ISSUE #3)
                         # Only reset if shift is > strike_step/2 (e.g., > 25 for NIFTY)
                         # This prevents micro-resets from spot price bouncing
                         ATM_SHIFT_THRESHOLD = self.strike_step / 2
                         spot_shift = abs(new_atm - self.current_atm)
                         
                         if spot_shift >= ATM_SHIFT_THRESHOLD:
                             # Significant shift detected - check cooldown
                             now_ts = datetime.now().timestamp()
                             if now_ts - self.last_reset_ts < 5.0:
                                 if loop_count % 20 == 0:
                                     logger.debug(f"[ATM][SKIP] Cooldown active (shift={spot_shift:.0f}, threshold={ATM_SHIFT_THRESHOLD:.0f})")
                             elif not self.reset_in_progress:
                                 self.reset_in_progress = True
                                 self.last_reset_ts = now_ts
                                 logger.warning(f"[ATM][SHIFT] {self.current_atm:.0f} -> {new_atm:.0f} (Spot={ltp:.2f}, Delta={spot_shift:.0f})")
                                 asyncio.create_task(self._reset_feed_for_new_atm(new_atm))
                         else:
                             # Minor fluctuation - ignore (hysteresis working)
                             if loop_count % 100 == 0:
                                 logger.debug(f"[ATM][MINOR] Spot {ltp:.2f} -> ATM {new_atm:.0f} (within hysteresis, no reset)")

                # 🟢 PHASE 3: SEQUENCE NUMBER
                current_seq = self.seq_map.get(key, 0) + 1
                self.seq_map[key] = current_seq

                # Capture Receive Timestamp
                recv_ts_val = int(datetime.now().timestamp() * 1000)
                
                # Try to get Broker Timestamp
                broker_ts_val = 0
                if "ltt" in feed_data:
                     try:
                         broker_ts_val = int(feed_data.get("ltt", 0))
                     except: pass
                elif "timestamp" in feed_data:
                     try:
                         ts_raw = feed_data.get("timestamp")
                         if isinstance(ts_raw, int): broker_ts_val = ts_raw
                     except: pass

                # ✅ CRITICAL FIX: Precision (Decimal)
                # Store prices as strings/decimals to avoid float drift
                # Redis expects strings anyway.
                
                data = {
                    "ltp": str(ltp) if ltp is not None else "0",
                    "volume": volume,
                    "oi": oi,
                    "seq": current_seq,
                    "recv_ts": recv_ts_val,
                    # ✅ Include Depth Data
                    "bid": bid,
                    "ask": ask,
                    "bid_qty": bid_qty,
                    "ask_qty": ask_qty
                }
                
                if broker_ts_val > 0:
                    data["broker_ts"] = broker_ts_val
                    self.tick_metrics["last_broker_ts"] = broker_ts_val
                    
                    gap = (recv_ts_val - broker_ts_val)
                    if gap > self.tick_metrics["max_gap_ms"]:
                         self.tick_metrics["max_gap_ms"] = gap
                
                if broker_iv > 0:
                    data["iv"] = broker_iv # Greeks can remain float/str
                    if broker_delta != 0:
                         data["delta"] = broker_delta
                         data["theta"] = broker_theta
                         data["gamma"] = broker_gamma
                         data["vega"] = broker_vega
                
                elif key != self.underlying_key and self.spot_ltp > 0 and self.expiry_date:
                    last_calc = self.last_greeks_calc.get(key)
                    if last_calc and (current_time - last_calc).total_seconds() < 1.0:
                        pass 
                    else:
                        self.last_greeks_calc[key] = current_time
                        # Greeks calc expects floats, so convert momentarily (safe for Greeks)
                        asyncio.create_task(self._calculate_and_update_greeks(key, float(ltp), data))
                
                # 🚀 Add to Update Buffer
                self.update_buffer[key] = data
            
                # ⚡ TRIGGER EXECUTION ENGINE - REMOVED PER TICK
                # Moved to _execution_monitor_loop (1s polling)
                # if key == self.underlying_key or (self.spot_ltp > 0):
                #      asyncio.create_task(self._trigger_pending_orders(key))


                last_redis = self.last_redis_update.get(key)
                if not last_redis or (current_time - last_redis).total_seconds() > 0.25: 
                     try:
                         # ✅ PHASE 2: Smart Fallback with All Critical Fixes
                         # FIX #2: Conditional timestamp updates
                         # WHY: Only update timestamps when REAL depth received
                         
                         if "bid" not in data or float(data.get("bid", 0)) == 0:
                             data["bid"] = data["ltp"]
                             data["bid_simulated"] = True
                         else:
                             data["bid_simulated"] = False
                         
                         if "ask" not in data or float(data.get("ask", 0)) == 0:
                             data["ask"] = data["ltp"]
                             data["ask_simulated"] = True
                         else:
                             data["ask_simulated"] = False
                         
                         # Quantities: preserve real or simulate
                         if "bid_qty" not in data or data.get("bid_qty", 0) == 0:
                             data["bid_qty"] = 100000
                         if "ask_qty" not in data or data.get("ask_qty", 0) == 0:
                             data["ask_qty"] = 100000
                         
                         # FIX #2: Only update timestamps when REAL depth received
                         # WHY: Prevents "false freshness" when LTP updates but depth doesn't
                         if not data.get("bid_simulated", True) and not data.get("ask_simulated", True):
                             # Real depth received - update timestamps
                             data["bid_ts"] = recv_ts_val
                             data["ask_ts"] = recv_ts_val
                         else:
                             # Simulated or missing - preserve old timestamps (or 0 if never set)
                             data["bid_ts"] = data.get("bid_ts", 0)
                             data["ask_ts"] = data.get("ask_ts", 0)
                         
                         # FIX #3: Calculate spread with zero-division protection
                         # WHY: Prevents runtime errors on malformed packets
                         if float(data.get("bid", 0)) > 0 and float(data.get("ask", 0)) > 0:
                             spread = float(data["ask"]) - float(data["bid"])
                             # Protect against zero bid (malformed packet)
                             if float(data["bid"]) > 0:
                                 spread_pct = (spread / float(data["bid"])) * 100
                             else:
                                 spread_pct = 0
                             data["spread"] = spread
                             data["spread_pct"] = spread_pct
                         else:
                             data["spread"] = 0
                             data["spread_pct"] = 0

                         payload = data.copy()
                         payload['timestamp'] = datetime.utcnow().isoformat()
                         
                         await redis_manager.set_market_data(key, payload)
                         self.last_redis_update[key] = current_time
                         
                         last_trigger = self.last_execution_trigger.get(key)
                         if key == self.underlying_key or (self.spot_ltp > 0): 
                             if not last_trigger or (current_time - last_trigger).total_seconds() > 0.2: 
                                 self.last_execution_trigger[key] = current_time
                                 # asyncio.create_task(self._trigger_pending_orders(key, data)) # DISABLED for Polling

                     
                     except Exception as e:
                         logger.error(f"Redis/Trigger error: {e}")

        except Exception as e:
            logger.error(f"[_process_data] Critical error: {e}", exc_info=True)
            
            # ⚠️ SAFETY CHECK: Only access key/data if bound
            if 'key' in locals() and 'data' in locals():
                if key in self.update_buffer:
                    self.update_buffer[key].update(data)
                else:
                    self.update_buffer[key] = data
            
                if len(self.update_buffer) == 1:
                    logger.info(f"📊 First data added to buffer: {key} -> LTP={ltp if 'ltp' in locals() else '?'}")

    async def _trigger_pending_orders(self, instrument_key: str, market_data: dict = None):
        """
        Trigger execution engine for a specific instrument.
        runs in a separate task.
        """
        from .database import AsyncSessionLocal
        from .execution_engine import check_pending_orders
        
        try:
            async with AsyncSessionLocal() as db:
                await check_pending_orders(instrument_key, db, market_data=market_data)
        except Exception as e:
            # excessive logging here might be bad if it fails often, but vital for debug now
            logger.error(f"Failed to trigger pending orders for {instrument_key}: {e}")

    async def _calculate_and_update_greeks(self, key, ltp, data_ref):
        """
        Helper task to calculate Greeks without blocking.
        Updates the buffer directly when done.
        """
        try:
            # 1. Get Details
            details = instrument_manager.get_instrument_details(key)
            strike = None
            option_type = None

            if details:
                strike = details.get("strike")
                option_type = details.get("option_type")
            else:
                 # Fallback parsing
                 parts = key.split('|')
                 if len(parts) >= 2:
                     last_part = parts[-1].upper()
                     if 'CE' in last_part:
                         option_type = 'CE'
                         strike_str = last_part.replace("CE", "").strip()
                     elif 'PE' in last_part:
                         option_type = 'PE'
                         strike_str = last_part.replace("PE", "").strip()
                     
                     if strike_str and option_type:
                         import re
                         match = re.search(r"(\d+(\.\d+)?)", strike_str)
                         if match: strike = float(match.group(1))

            if strike and option_type:
                # 2. Run blocking math in executor
                greeks = await self.loop.run_in_executor(
                    None, 
                    calculate_greeks, 
                    self.spot_ltp, strike, self.days_to_expiry_val(), ltp, option_type
                )
                
                # 3. Update Buffer
                if key in self.update_buffer:
                    self.update_buffer[key].update(greeks)
                else:
                    # If key is gone from buffer (flushed), create new entry
                    # We need to re-add LTP/OI for context or just send partial update?
                    # Sending partial update is fine, frontend handles merge.
                    self.update_buffer[key] = greeks

        except Exception as e:
            # logger.error(f"Async Greeks error for {key}: {e}")
            pass 
                 
    def days_to_expiry_val(self):
        if not self.expiry_date: return 0.0
        try:
            # Parse expiry date (YYYY-MM-DD)
            expiry_dt = datetime.strptime(self.expiry_date, "%Y-%m-%d")
            
            # Set expiry time to 15:30:00 (Indian Market Close)
            expiry_dt = expiry_dt.replace(hour=15, minute=30, second=0)
            
            today = datetime.now()
            diff = expiry_dt - today
            
            # Return fractional days (seconds / 86400)
            return diff.total_seconds() / 86400.0
        except Exception as e:
            return 0.0

    async def subscribe(self, keys: list):
        """
        ⚠️ DEPRECATED: Use switch_underlying() instead.
        
        SESSION-BOUND Rule: Cannot modify subscriptions on active session.
        To change instruments, hard-switch to new session.
        """
        if not keys: return
        
        logger.warning("⚠️ subscribe() called - This is deprecated in SESSION-BOUND mode")
        logger.warning("💡 Use switch_underlying() to change instruments")
        
        # For initial subscription (before connection), allow it
        if self.connection_state == "NOT_CONNECTED":
            logger.info(f"📋 Initial subscription: {len(keys)} instruments")
            self.subscriptions.update(keys)
        else:
            logger.error("❌ Cannot modify active session. Hard-switch required.")
            logger.error("🔄 Call switch_underlying(new_key, new_instruments) instead")

    async def switch_underlying(self, new_underlying_key: str, new_instrument_keys: list):
        """
        SESSION-BOUND hard switch: Completely close old session, create new one.
        
        This is the ONLY way to change instruments in V3.
        
        Args:
            new_underlying_key: New underlying instrument key
            new_instrument_keys: IGNORED (Backend calculates subscription list)
        """
        # 🔒 HARD STATE GUARD: Prevent race conditions
        if self.connection_state in ("SWITCHING", "DISCONNECTING"):
            logger.warning(f"Switch ignored: feed is {self.connection_state}")
            return

        self.connection_state = "SWITCHING"

        logger.info("="*70)
        logger.info(f"🔄 HARD SWITCH: {self.underlying_key} → {new_underlying_key}")
        logger.info("="*70)
        
        # Step 1: Hard close old session
        await self._hard_close()
        
        # Step 2: Update configuration for new session
        # ✅ FIX: Resolve key before switching
        from .instrument_manager import instrument_manager
        resolved_key = instrument_manager.resolve_instrument_key(new_underlying_key)
        logger.info(f"🔄 Resolved Switch Key: {new_underlying_key} -> {resolved_key}")
        
        self.underlying_key = resolved_key
        
        # ✅ FIX: Prioritize Spot Price & Limit Subscriptions
        # Upstox V3 often has limits (e.g. 100 symbols). If we exceed, we might lose the Spot Price.
        # We MUST ensure the underlying key is in the list and prioritized.
        
        # 🟢 PHASE 1: DETERMINISTIC SUBSCRIPTION (Assessment)
        # Old Greedy Logic Removed. New Logic:
        
        # 1. Get Spot & Expiry Details
        # We need to know the expiry to build keys like "NSE_FO|NIFTY26JAN23000CE"
        # Since 'new_instrument_keys' is passed from frontend, we can extract details from there 
        # OR better: Use Instrument Manager to get definitive details.
        
        from .instrument_manager import instrument_manager
        
        # Try to deduce strike step and expiry from the requested keys if possible,
        # otherwise default to Nifty standard.
        # Ideally, we should fetch "Master Config" for this underlying.
        # For now, we trust the 'instrument_manager' to resolve keys.
        
        # 2. Priority: SPOT KEY
        final_subs = set()
        final_subs.add(resolved_key)
        
        # 🟢 FIX #1: Respect Frontend Keys (PRIORITY FIX - FIXES ISSUE #3)
        # Frontend has already calculated optimal keys sorted by distance to ATM.
        # If frontend provides keys, use them directly instead of waiting for first tick reset.
        # This saves 100-200ms and eliminates unnecessary disconnect/reconnect.
        
        # ✅ FIX: Removed arbitrary "len > 2" check. Trust frontend keys if provided.
        if new_instrument_keys and len(new_instrument_keys) > 0:
            # Frontend keys available - use them directly
            logger.info(f"✅ [FIX#1] Using frontend-provided keys ({len(new_instrument_keys)} instruments)")
            logger.info(f"   Keys are already prioritized by distance to spot")
            final_subs.update(new_instrument_keys)
            
            # FIX #2: Initialize current_atm from frontend context (FIXES ISSUE #2)
            # Deduce ATM from the keys to prevent unnecessary reset on first tick
            try:
                from .instrument_manager import instrument_manager
                # Extract strike prices from instrument keys to estimate ATM
                strikes_in_keys = []
                for key in list(new_instrument_keys):
                    if key != resolved_key:  # Skip underlying key
                        details = instrument_manager.get_instrument_details(key)
                        if details and details.get('strike'):
                            strikes_in_keys.append(float(details.get('strike', 0)))
                
                if strikes_in_keys:
                    # ATM is the middle strike (frontend prioritizes by distance)
                    estimated_atm = sorted(strikes_in_keys)[len(strikes_in_keys)//2]
                    self.current_atm = estimated_atm
                    logger.info(f"📍 [FIX#2] Initialized ATM={self.current_atm} from frontend keys")
                    logger.info(f"   This prevents unnecessary reset on first tick")
                else:
                    self.current_atm = None
            except Exception as e:
                logger.warning(f"Could not deduce ATM from keys: {e}")
                self.current_atm = None
            
        else:
            # Fallback: No frontend keys - use dynamic "spot-only then reset" strategy
            logger.warning(f"⚠️ [FIX#1] No frontend keys provided, falling back to dynamic mode")
            logger.info(f"🔄 Hard Switch Strategy: Connecting to SPOT ({resolved_key}) only first.")
            logger.info("   Full option chain will subscribe automatically on first tick.")
            final_subs.add(resolved_key)
            self.current_atm = None  # Reset ATM so first tick triggers detection
        
        # 🚀 IMMEDIATE CLEAR: Tell frontend to clear old data
        # This prevents "Ghost Ticks" from persistent memory while we switch
        await self._broadcast_feed_state("RESETTING", 0, [], reason="SWITCH_UNDERLYING")
        
        self.subscriptions = final_subs
        
        self.underlying_key = resolved_key
        # ✅ FIX: Update Strike Step & Reset Expiry
        try:
            # We must use the resolved key to get the correct step
            self.strike_step = instrument_manager.get_strike_step(resolved_key)
            self.instrument_expiry = None # Force re-fetch of expiry for new instrument
            logger.info(f"   Strike Step updated to: {self.strike_step}")
        except Exception as e:
            logger.error(f"Failed to update strike step: {e}")
            self.strike_step = 50 # Safe default?

        self.session_locked = False
        
        logger.info(f"📋 New session config: Spot Only (Auto-Expand on Tick)")
        logger.info(f"   Spot Key Included: {resolved_key in self.subscriptions}")
        logger.info(f"   Subscriptions: {self.subscriptions}") # Added debug
        
        # Step 3: Wait for cleanup
        await asyncio.sleep(2.0)
        
        # Step 4: Create fresh session
        logger.info("🚀 Launching new feed session...")
        asyncio.create_task(self.connect_and_run())
    
    async def _hard_close(self):
        """Completely destroy current feed session - no graceful cleanup."""
        logger.info("🔨 HARD CLOSE: Destroying current feed session")
        
        self.connection_state = "DISCONNECTING"
        self.keep_running = False
        self.session_locked = False
        
        # Kill broadcast loop - Thread-safe Fix
        if self.broadcast_task:
            if isinstance(self.broadcast_task, asyncio.Task):
                self.broadcast_task.cancel()
                try:
                    await self.broadcast_task
                except asyncio.CancelledError:
                    pass
            else:
                # It's a concurrent.futures.Future (from run_coroutine_threadsafe)
                # We CANNOT await it in this loop directly if it wasn't wrapped,
                # and run_coroutine_threadsafe returns a concurrent Future.
                self.broadcast_task.cancel()
            
            self.broadcast_task.cancel()
            
            self.broadcast_task = None
        
        # Kill Execution Monitor
        if self.execution_task:
            if isinstance(self.execution_task, asyncio.Task):
                self.execution_task.cancel()
            else:
                 self.execution_task.cancel()
            self.execution_task = None

        
        # Kill WebSocket feed
        if self.custom_feed:
            try:
                await self.custom_feed.disconnect()
                logger.info("✅ WebSocket disconnected")
            except Exception as e:
                logger.error(f"Error during WS disconnect: {e}")
        
        # Clear state
        self.custom_feed = None
        self.subscriptions.clear()
        self.update_buffer.clear()
        self.connection_state = "NOT_CONNECTED"
        
        logger.info("✅ Hard close complete - session destroyed")
    
    async def stop(self, restart=False):
        """Graceful stop (for shutdown, not for switching)."""
        logger.info(f"🛑 Graceful stop requested (Restart={restart})")
        await self._hard_close()
    
    async def unsubscribe(self, keys: list):
        """
        ❌ NOT SUPPORTED in Upstox V3 SESSION-BOUND mode.
        
        Frontend must NOT call this. Unsubscribe requests are IGNORED.
        To change instruments, call switch_underlying() instead.
        """
        logger.warning("⚠️ unsubscribe() called - NOT SUPPORTED in SESSION-BOUND mode")
        logger.warning(f"📋 Requested to unsubscribe: {len(keys)} instruments")
        logger.warning("🚫 Request IGNORED - feed state unchanged")
        logger.warning("💡 Use switch_underlying() to change instruments instead")
        
        # DO NOTHING - this is intentional
        # Unsubscribe failure ≠ Feed failure
    
    async def _send_market_closed_event(self):
        """Notify frontend that market is closed - use REST only."""
        try:
            await self.user_ws.send_text(json.dumps({
                "type": "MARKET_STATUS",
                "status": "CLOSED",
                "msg": "Market is closed. Displaying REST API data only.",
                "ws_disabled": True
            }))
            logger.info("✅ Sent MARKET_STATUS:CLOSED to frontend")
        except Exception as e:
            logger.error(f"Failed to send market closed event: {e}")
