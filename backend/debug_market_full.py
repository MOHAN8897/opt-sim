import asyncio
import logging
import os
import sys
import json
from datetime import datetime

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("debug_full")

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.market_feed import UpstoxFeedBridge, UpstoxAuthWrapper
from backend.instrument_manager import instrument_manager
from backend.database import AsyncSessionLocal
from backend.models import UpstoxAccount, UpstoxStatus
from sqlalchemy.future import select
from backend.broker import decrypt
from backend.greeks_calculator import calculate_greeks

# Mock WebSocket for printing output
class MockWebSocket:
    async def send_text(self, data):
        try:
            msg = json.loads(data)
            if msg.get("type") == "MARKET_UPDATE":
                updates = msg.get("data", {})
                for key, val in updates.items():
                    logger.info(f"UPDATE [ {key} ] LTP: {val.get('ltp')} | Vol: {val.get('volume')} | OI: {val.get('oi')} | IV: {val.get('iv')} | Delta: {val.get('delta')}")
        except:
            print(f"RAW WS MSG: {data}")

async def main():
    logger.info("Starting Debug Script...")

    # 1. Initialize Instrument Manager (needed for Greeks)
    logger.info("Initializing Instrument Manager...")
    await instrument_manager.initialize()
    logger.info("Instrument Manager Ready.")

    # 2. Get Valid Token from DB
    access_token = None
    async with AsyncSessionLocal() as db:
        stmt = select(UpstoxAccount).filter(UpstoxAccount.status == UpstoxStatus.TOKEN_VALID)
        result = await db.execute(stmt)
        account = result.scalars().first()
        if account and account.access_token:
            access_token = decrypt(account.access_token)
            logger.info(f"Found valid token for user {account.user_id}")
        else:
            logger.error("No valid Upstox token found in DB. Please login via UI first.")
            return

    # 3. Define Keys to Test
    # HDFC Bank (Equity) & NIFTY 50 (Index) & Some Options
    
    # Need to find correct keys first
    hdfc_key = "NSE_EQ|INE040A01034" # HDFCBANK EQ
    nifty_key = "NSE_INDEX|Nifty 50" # NIFTY 50
    
    # Find an active option for NIFTY
    expiry = instrument_manager.get_expiry_dates(nifty_key)[0] # Get nearest expiry
    chain = instrument_manager.get_option_chain(nifty_key, expiry, 25000, 1) # Get one mock chain around 25000
    
    test_keys = [hdfc_key, nifty_key]
    
    # Add one call and one put if available
    if chain:
        row = chain[0]
        if row['call_options']: test_keys.append(row['call_options']['instrument_key'])
        if row['put_options']: test_keys.append(row['put_options']['instrument_key'])
    
    logger.info(f"Testing Keys: {test_keys}")

    # 4. Initialize Bridge
    mock_ws = MockWebSocket()
    
    # We pass NIFTY 50 as underlying for Greeks calculation context
    bridge = UpstoxFeedBridge(
        user_ws=mock_ws,
        access_token=access_token,
        expiry_date=expiry,
        underlying_key=nifty_key 
    )

    # 5. Run Bridge
    # Start the bridge loop
    bridge_task = asyncio.create_task(bridge.connect_and_run())
    
    # Wait a bit for connection
    await asyncio.sleep(2)
    
    # Subscribe
    await bridge.subscribe(test_keys)
    
    # Run for 15 seconds
    logger.info("Listening for 15 seconds...")
    await asyncio.sleep(15)
    
    # Stop
    await bridge.stop()
    bridge_task.cancel()
    logger.info("Test Complete.")

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
