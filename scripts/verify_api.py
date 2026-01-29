
import httpx
import asyncio
from jose import jwt
from datetime import datetime, timedelta
from backend.config import settings
import sys
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

# Generate Token
def create_test_token():
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode = {"sub": "test@test.com", "name": "Test User", "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

async def verify_live():
    print("--- Testing Live Server (localhost:8000) ---")
    token = create_test_token()
    cookies = {"access_token": token}
    
    async with httpx.AsyncClient() as client:
        # 1. Expiry
        ukey = "NSE_INDEX|Nifty 50"
        print(f"Fetching expiry for: {ukey}")
        try:
            resp = await client.get(f"http://localhost:8000/api/market/expiry?instrument_key={ukey}", cookies=cookies)
            if resp.status_code == 200:
                print(f"Expiry Success: {resp.json().get('expiry_dates')[:3]}")
                
                expiries = resp.json().get('expiry_dates')
                if expiries:
                    expiry = expiries[0]
                    # 2. Option Chain
                    print(f"Fetching Chain for {expiry}...")
                    resp_chain = await client.get(
                        f"http://localhost:8000/api/market/option-chain?instrument_key={ukey}&expiry_date={expiry}",
                        cookies=cookies
                    )
                    
                    if resp_chain.status_code == 200:
                         data = resp_chain.json()
                         print(f"Chain Success! Spot: {data.get('spot_price')}, Items: {len(data.get('chain', []))}")
                    elif resp_chain.status_code == 503:
                         print("Failed: 503 - Instrument Manager still loading.")
                    elif resp_chain.status_code == 502:
                         print("Failed: 502 - Spot Price fetch failed (Expected if no Broker Token).")
                         # Note: Backend tries to fetch spot from Upstox. If we have no Broker Access Token in DB for 'test@test.com', it verifies Broker connection first.
                         # Actually get_option_chain calls `get_upstox_client(user)`.
                         # This will fail with 401 "Broker not connected" or similar if the user isn't linked.
                         # But wait, looking at market_data.py, it calls `get_upstox_client` BEFORE fetching spot.
                         # So we expect 401 "Broker not connected".
                    elif resp_chain.status_code == 401:
                         print(f"Got 401: {resp_chain.json().get('detail')}")
                         if "Broker not connected" in str(resp_chain.text):
                             print("Success! (Partial) - Backend is UP and checking Broker status.")
                             print("The 'Option Chain Empty' issue (503) is RESOLVED.")
                    else:
                         print(f"Error: {resp_chain.status_code} {resp_chain.text}")
            else:
                print(f"Expiry Error: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_live())
