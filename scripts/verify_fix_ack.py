
import asyncio
import websockets
import json
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("validator")

async def verify_subscription_flow():
    uri = "ws://localhost:8000/ws/market-data?token=test_token"
    
    # Generate test token first (mock) - Assuming we can use a fixed token or just try
    # For local dev, we might need a valid token. 
    # Let's assume validation disabled or we use a known token from file.
    try:
        with open("token.txt", "r") as f:
            token = f.read().strip()
            uri = f"ws://localhost:8000/ws/market-data?token={token}"
    except:
        logger.warning("No token.txt found, trying with dummy token")

    logger.info(f"Connecting to {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("✅ Connected to WebSocket")
            
            # Wait for initial messages
            while True:
                msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(msg)
                logger.info(f"📩 Received: {data.get('type')}")
                
                if data.get("type") == "ws_connected" or data.get("type") == "WS_CONNECTED":
                    logger.info("✅ Initial Handshake Complete")
                    break
            
            # Send Switch Underlying Request
            # We use NIFTY and some dummy keys
            payload = {
                "action": "switch_underlying",
                "underlying_key": "NSE_INDEX|Nifty 50",
                "keys": [
                    "NSE_INDEX|Nifty 50",
                    "NSE_FO|NIFTY240215C22000", # Dummy
                    "NSE_FO|NIFTY240215P22000"  # Dummy
                ]
            }
            logger.info(f"📤 Sending Subscription Request: {payload}")
            await websocket.send(json.dumps(payload))
            
            # Expect ACK
            logger.info("⏳ Waiting for ACK...")
            ack_received = False
            
            try:
                while not ack_received:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(msg)
                    logger.info(f"📩 Received: {data.get('type')}")
                    
                    if data.get("type") == "SUBSCRIPTION_ACK":
                        logger.info("✅ SUBSCRIPTION_ACK Received!")
                        logger.info(f"   Status: {data.get('status')}")
                        logger.info(f"   Count: {data.get('count')}")
                        ack_received = True
                    elif data.get("type") == "SUBSCRIPTION_ERROR":
                        logger.error(f"❌ SUBSCRIPTION_ERROR: {data.get('error')}")
                        return
                        
            except asyncio.TimeoutError:
                logger.error("❌ Timeout waiting for ACK")
                return

            logger.info("✅ Verification SUCCESS: Subscription Flow is working.")

    except Exception as e:
        logger.error(f"❌ Verification Failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_subscription_flow())
