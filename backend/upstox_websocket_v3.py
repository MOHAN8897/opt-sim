"""
Custom WebSocket handler for Upstox Market Data Feed V3
Uses authorized WebSocket URL and protobuf encoding/decoding
"""
import asyncio
import json
import logging
import httpx
import websockets
import uuid
import time
from typing import Set, Callable, Optional
from collections import defaultdict

try:
    from . import MarketDataFeedV3_pb2
except ImportError:
    import MarketDataFeedV3_pb2

logger = logging.getLogger("api.feed_custom")

class UpstoxWebSocketFeed:
    """
    Custom WebSocket implementation that properly uses Upstox V3 authorization.
    
    This replaces MarketDataStreamerV3 SDK because the SDK doesn't support
    using the authorized_redirect_uri from the authorize endpoint.
    """
    
    def __init__(
        self,
        access_token: str,
        instrument_keys: Set[str],
        on_message: Callable,
        on_open: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_close: Optional[Callable] = None,
    ):
        self.access_token = access_token
        # ✅ FIX: Create a COPY of the set to prevents Race Conditions
        # If the parent clears the set (e.g. during hard close), this instance
        # typically should still have its own immutable view for the connection attempt.
        self.instrument_keys = set(instrument_keys) if instrument_keys else set()
        self.on_message_callback = on_message
        self.on_open_callback = on_open
        self.on_error_callback = on_error
        self.on_close_callback = on_close
        
        self.websocket = None
        self.authorized_url = None
        self.is_running = False
        
        # Tick aggregation for logging
        self.tick_counts = defaultdict(int)
        self.last_log_time = time.time()
        self.total_ticks = 0
        
    async def get_authorized_url(self) -> str:
        """
        Call Upstox authorize endpoint to get the one-time WebSocket URL.
        
        Returns:
            str: The authorized WebSocket URL (wss://...)
        """
        logger.info("🔐 Calling WebSocket authorization endpoint...")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.upstox.com/v3/feed/market-data-feed/authorize",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json"
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Authorization failed: {response.status_code} - {response.text}")
            
            data = response.json()
            if data.get("status") != "success":
                raise Exception(f"Authorization response not successful: {data}")
            
            authorized_url = data["data"]["authorized_redirect_uri"]
            logger.info(f"✅ Got authorized WebSocket URL (length: {len(authorized_url)})")
            return authorized_url
    
    def encode_subscription_message(self) -> bytes:
        """
        Encode subscription message in protobuf binary format.
        
        Note: Upstox documentation shows this should be a simple subscribe message.
        The exact format might need adjustment based on actual API behavior.
        """
        # Create subscription request (this might need adjustment based on actual Upstox protocol)
        # Currently sending as JSON wrapped in binary - may need pure protobuf
        sub_message = {
            "guid": str(uuid.uuid4()),
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": list(self.instrument_keys)
            }
        }
        
        # For now, send as JSON bytes - Upstox SDK does internal conversion
        # TODO: If this doesn't work, implement proper protobuf encoding
        return json.dumps(sub_message).encode('utf-8')
    
    def decode_market_data(self, binary_data: bytes) -> dict:
        """
        Decode protobuf binary message to Python dict.
        
        Args:
            binary_data: Raw binary protobuf data
            
        Returns:
            dict: Decoded market data
        """
        try:
            # Decode protobuf message
            feed_response = MarketDataFeedV3_pb2.FeedResponse()
            feed_response.ParseFromString(binary_data)
            
            # Convert to dict for processing
            result = {}
            
            for instrument_key, feed in feed_response.feeds.items():
                data = {"instrument_key": instrument_key}
                
                # Extract LTPC data
                if feed.HasField("ltpc"):
                    ltpc = feed.ltpc
                    data["ltp"] = ltpc.ltp
                    data["close_price"] = ltpc.cp
                
                # Extract Full Feed data (includes Greeks, OI, IV)
                elif feed.HasField("fullFeed"):
                    full = feed.fullFeed
                    
                    if full.HasField("marketFF"):
                        market = full.marketFF
                        if market.HasField("ltpc"):
                            data["ltp"] = market.ltpc.ltp
                            data["close_price"] = market.ltpc.cp
                        
                        if market.HasField("optionGreeks"):
                            greeks = market.optionGreeks
                            data["delta"] = greeks.delta
                            data["theta"] = greeks.theta
                            data["gamma"] = greeks.gamma
                            data["vega"] = greeks.vega
                        
                        data["oi"] = market.oi
                        data["iv"] = market.iv
                        data["volume"] = market.vtt
                        
                        # 🟢 Extracts Market Depth (Bid/Ask)
                        # We use min(asks) and max(bids) because depth is not guaranteed to be sorted
                        if market.HasField("marketLevel"):
                            quotes = market.marketLevel.bidAskQuote
                            if quotes:
                                best_bid = 0.0
                                best_ask = 0.0
                                bid_qty = 0
                                ask_qty = 0
                                
                                # Extract all valid non-zero prices
                                valid_bids = [q for q in quotes if q.bidP > 0]
                                valid_asks = [q for q in quotes if q.askP > 0]
                                
                                if valid_bids:
                                    # Highest Bid is Best
                                    best_bid_quote = max(valid_bids, key=lambda q: q.bidP)
                                    best_bid = best_bid_quote.bidP
                                    bid_qty = best_bid_quote.bidQ
                                    
                                if valid_asks:
                                    # Lowest Ask is Best
                                    best_ask_quote = min(valid_asks, key=lambda q: q.askP)
                                    best_ask = best_ask_quote.askP
                                    ask_qty = best_ask_quote.askQ
                                    
                                data["bid"] = best_bid
                                data["ask"] = best_ask
                                data["bid_qty"] = bid_qty
                                data["ask_qty"] = ask_qty
                
                result[instrument_key] = data
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to decode protobuf message: {e}")
            return {}
    
    async def connect(self):
        """
        Connect to Upstox WebSocket using authorized URL.
        
        CRITICAL: authorized_redirect_uri is SINGLE-USE.
        We MUST re-authorize on every reconnect.
        """
        try:
            # 🚨 ALWAYS get fresh URL - URLs are single-use
            self.authorized_url = await self.get_authorized_url()
            
            logger.info(f"📡 Connecting to authorized WebSocket...")
            logger.info("Connecting to WS | headers=NONE | using authorized_redirect_uri")
            
            # 🚨 IDEMPOTENCY GUARD: Prevent duplicate connections
            if not self.instrument_keys or len(self.instrument_keys) == 0:
                logger.error("❌ PROTOCOL VIOLATION PREVENTED: Cannot subscribe with 0 instruments")
                return

            # Log protocol for debugging
            protocol = self.authorized_url.split(":")[0]
            logger.info(f"✅ Got authorized WebSocket URL (Protocol: {protocol}, length: {len(self.authorized_url)})")

            if protocol.startswith("http"):
                logger.warning(f"⚠️ URL starts with {protocol}, but we expect wss/ws. Library might handle it or fail.")

            # Connect to WebSocket WITHOUT headers
            # CRITICAL: authorized_redirect_uri already embeds auth - headers break the handshake
            # We explicitly strip User-Agent to avoid fingerprinting blocks
            async with websockets.connect(
                self.authorized_url, 
                # user_agent_header="Upstox-Python-Client/3.0", # Removed to match successful debug baseline
                open_timeout=10,
                ping_interval=None # Disable auto-ping to avoid interference, let Upstox handle it? Or default.
            ) as websocket:
                self.websocket = websocket
                self.is_running = True
                
                logger.info("✅ WebSocket connected!")
                
                # Trigger on_open callback
                if self.on_open_callback:
                    self.on_open_callback()
                
                # Send subscription message
                logger.info(f"📨 Sending subscription for {len(self.instrument_keys)} instruments...")
                subscription_msg = self.encode_subscription_message()
                await websocket.send(subscription_msg)
                
                # Reset tick tracking
                self.tick_counts = defaultdict(int)
                self.last_log_time = time.time()
                self.total_ticks = 0
                
                # Receive messages loop
                async for message in websocket:
                    if not self.is_running:
                        break
                    
                    try:
                        # Decode binary protobuf message
                        decoded_data = self.decode_market_data(message)
                        
                        if decoded_data and self.on_message_callback:
                            # Track ticks for logging
                            self.total_ticks += 1
                            for key in decoded_data.keys():
                                self.tick_counts[key] += 1
                            
                            # Log aggregated tick counts every 5 seconds
                            current_time = time.time()
                            if current_time - self.last_log_time >= 5.0:
                                self._log_tick_summary()
                                self.last_log_time = current_time
                            
                            self.on_message_callback(decoded_data)
                    
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        if self.on_error_callback:
                            self.on_error_callback(e)
        
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
        
        except Exception as e:
            logger.error(f"Connection error: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
        
        finally:
            self.is_running = False
            if self.on_close_callback:
                self.on_close_callback()
    
    def _log_tick_summary(self):
        """
        Log aggregated tick counts to avoid console spam.
        """
        if self.total_ticks == 0:
            logger.info("📊 Tick Summary (5s): No ticks received")
            return
        
        # Group instruments by tick count ranges
        ranges = {
            "1-5": 0,
            "6-20": 0,
            "21-50": 0,
            "51+": 0
        }
        
        for count in self.tick_counts.values():
            if count <= 5:
                ranges["1-5"] += 1
            elif count <= 20:
                ranges["6-20"] += 1
            elif count <= 50:
                ranges["21-50"] += 1
            else:
                ranges["51+"] += 1
        
        logger.info(f"📊 Tick Summary (5s): Total={self.total_ticks} ticks | " +
                   f"Instruments: {ranges['1-5']} (1-5 ticks), {ranges['6-20']} (6-20), " +
                   f"{ranges['21-50']} (21-50), {ranges['51+']} (51+)")
        
        # Reset counters
        self.tick_counts = defaultdict(int)
        self.total_ticks = 0
    
    async def disconnect(self):
        """
        Disconnect from WebSocket.
        """
        self.is_running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket disconnected")
    
    def subscribe(self, instrument_keys: list):
        """
        Add instruments to subscription set.
        Note: For V3, you need to reconnect to add new subscriptions.
        """
        self.instrument_keys.update(instrument_keys)
        logger.info(f"Added {len(instrument_keys)} instruments to subscription set")
    
    def unsubscribe(self, instrument_keys: list):
        """
        Remove instruments from subscription set.
        """
        self.instrument_keys.difference_update(instrument_keys)
        logger.info(f"Removed {len(instrument_keys)} instruments from subscription set")
