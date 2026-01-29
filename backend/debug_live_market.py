import asyncio
import logging
import json
import os
import sys

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import AsyncSessionLocal
from sqlalchemy.future import select
from backend.models import UpstoxAccount, User, UpstoxStatus
from backend.broker import decrypt
from backend.instrument_manager import instrument_manager
from backend.greeks_calculator import calculate_greeks
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
import threading
from datetime import datetime

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("debug_live_feed")

class UpstoxAuthWrapper:
    """Wrapper to make string token look like API Client config"""
    def __init__(self, token):
        self.token = token
    class Config:
        def __init__(self, token):
            self.token = token
        def auth_settings(self):
            return {"OAUTH2": {"value": f"Bearer {self.token}"}}
    @property
    def configuration(self):
        return self.Config(self.token)

async def get_valid_token():
    async with AsyncSessionLocal() as db:
        # Get first available account with token
        stmt = select(UpstoxAccount).where(UpstoxAccount.status == UpstoxStatus.TOKEN_VALID)
        result = await db.execute(stmt)
        account = result.scalars().first()
        
        if not account or not account.access_token:
            logger.error("No valid Upstox token found in DB.")
            return None
            
        return decrypt(account.access_token)

def on_open(*args):
    logger.info("✅ Upstox WebSocket Connected.")

def on_error(error):
    logger.error(f"❌ Upstox WebSocket Error: {error}")
    if "403" in str(error) or "Forbidden" in str(error):
        logger.critical("!!! 403 Forbidden DETECTED !!! Token is likely invalid.")

def on_message(message):
    try:
        # logger.info(f"Raw Message: {json.dumps(message)[:200]}...") # Limit output
        
        feeds = message.get("feeds", {})
        if not feeds: return

        for key, feed_data in feeds.items():
            ff = feed_data.get("fullFeed", {})
            mff = ff.get("marketFF") or ff.get("indexFF", {})
            
            # LTP
            ltp = 0.0
            ltpc = mff.get("ltpc", {})
            ltp = float(ltpc.get("ltp", 0))
            if ltp == 0 and "ltpc" in feed_data:
                ltp = float(feed_data["ltpc"].get("ltp", 0))

            # Volume & OI
            volume = int(mff.get("vtt", 0))
            oi = int(mff.get("oi", 0))
            
            logger.info(f"Instrument: {key} | LTP: {ltp} | Vol: {volume} | OI: {oi}")
            
    except Exception as e:
        logger.error(f"Error parsing message: {e}")

async def main():
    logger.info("Starting Live Feed Debugger...")
    
    # 1. Get Token
    token = await get_valid_token()
    if not token:
        logger.error("Aborting: No Token.")
        return

    logger.info(f"Using Token: {token[:10]}...{token[-5:]}")

    # 2. Setup Streamer
    api_client = UpstoxAuthWrapper(token)
    
    # Sample Keys (Nifty Index & a likely Option)
    # Ideally get a valid key from instrument_manager
    # keys = ["NSE_INDEX|Nifty 50", "NSE_INDEX|Bank Nifty"]
    keys = ["NSE_INDEX|Nifty 50"] # Start simple
    
    streamer = MarketDataStreamerV3(api_client, keys, mode="full")
    
    streamer.on("open", on_open)
    streamer.on("error", on_error)
    streamer.on("message", on_message)
    
    streamer.auto_reconnect(True)
    
    # 3. Connect (Blocking)
    logger.info("Connecting to Upstox...")
    # Run in a thread to allow main async loop to wait
    t = threading.Thread(target=streamer.connect, daemon=True)
    t.start()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping...")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
