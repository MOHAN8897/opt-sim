
import os
import pymysql
import hashlib
import base64
import time
import requests
import json
from cryptography.fernet import Fernet
from upstox_client.feeder.market_data_streamer_v3 import MarketDataStreamerV3
import threading

# --- SECURITY ---
SECRET_KEY = "dev-secret-key-change-in-prod"
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r") as f:
        for line in f:
            if line.startswith("SECRET_KEY="):
                try: SECRET_KEY = line.strip().split("=", 1)[1].strip('"').strip("'"); break
                except: pass

def decrypt(data):
    try:
        key = hashlib.sha256(SECRET_KEY.encode()).digest()
        f = Fernet(base64.urlsafe_b64encode(key))
        if isinstance(data, memoryview): data = data.tobytes()
        return f.decrypt(data).decode()
    except Exception as e:
        print(f"Decrypt Error: {e}")
        return None

def get_access_token():
    conn = pymysql.connect(host="localhost", user="root", password="Sai@1234", database="paper_trading", port=3306)
    cursor = conn.cursor()
    cursor.execute("SELECT access_token FROM upstox_accounts WHERE status = 'TOKEN_VALID' LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return decrypt(row[0]) if row else None

# --- HELPER ---
def get_option_key(token):
    print("Searching for NIFTY option...")
    # 1. Get Spot
    url = "https://api.upstox.com/v2/market-quote/ltp?instrument_key=NSE_INDEX|Nifty 50"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"LTP Error: {resp.text}")
        return []
    
    nifty_ltp = resp.json()['data']['NSE_INDEX|Nifty 50']['last_price']
    print(f"Nifty LTP: {nifty_ltp}")
    
    # 2. Get Option Chain to find a key
    expiry = "2026-01-22" # Need a valid expiry. Hardcoding might fail. 
    # Better: Search instrument
    search_url = "https://api.upstox.com/v2/catalog/instrument/search"
    # Wait, simple search "NIFTY 25500 CE"
    # Actually, let's use the Option Chain API of UPSTOX if accessible, or just search.
    # Searching "NIFTY 2026" ??
    # Let's try searching for a generic symbol "NIFTY"
    params = {"instrument_key": "NSE_INDEX|Nifty 50", "expiry_date": "2026-01-22"} 
    # We need a dynamic expiry.
    # Let's just fetch the Option Chain from MY OWN BACKEND? 
    # Easier: GET http://localhost:8000/api/option-chain?instrument_key=NSE_INDEX|Nifty 50
    # But that requires auth.
    
    # Let's fallback to searching "BANKNIFTY" or "NIFTY" equity? No we need option.
    # Let's try to list expiry dates first?
    # Simpler: Subscribing to manual key guess: "NSE_FO|43242" (We don't know it).
    
    # Let's try to get Option Chain for NIFTY from Upstox API using the token.
    # We need valid expiry.
    # I will just use the hardcoded "NSE_INDEX|Nifty 50" for now to test "mode=option_greeks" behavior on Index?
    # Indices don't have Greeks.
    # I MUST find an option.
    
    # Let's generic search:
    q_url = "https://api.upstox.com/v2/market/quote/ltp?instrument_key=NSE_FO|47625" # Random?
    
    # BETTER: Use the `get_option_chain` logic from `backend/instrument_manager.py`?
    # I'll just try to fetch `https://api.upstox.com/v2/option/chain?instrument_key=NSE_INDEX|Nifty 50&expiry_date=2026-01-22`
    # (Assuming 2026-01-22 is close, based on user context `expiry_date=2026-01-20` in previous logs/image!)
    # Image says: Expiry: 2026-01-20
    # So I will use that.
    
    chain_url = "https://api.upstox.com/v2/option/chain"
    params = {"instrument_key": "NSE_INDEX|Nifty 50", "expiry_date": "2026-01-20"}
    resp = requests.get(chain_url, headers=headers, params=params)
    if resp.status_code == 200:
        data = resp.json().get('data', [])
        if data:
             # Pick first CE
             for item in data:
                 if 'call_options' in item:
                      key = item['call_options']['instrument_key']
                      print(f"Found Option Key: {key}")
                      return [key]
    else:
        print(f"Chain Error: {resp.text}")
    
    return ["NSE_INDEX|Nifty 50"]

# --- MOCK CLIENT ---
class MockAuthConfig:
    def __init__(self, token):
        self.token = token
    def auth_settings(self):
        return {"OAUTH2": {"value": f"Bearer {self.token}"}}
class MockApiClient:
    def __init__(self, token):
        self.configuration = MockAuthConfig(token)

def on_open(msg):
    print("✅ Connected.")

def on_message(message):
    print(f"⚡ TICK: {json.dumps(message, indent=2)}")

def on_error(e): print(f"Error: {e}")

def main():
    token = get_access_token()
    if not token: return
    
    keys = get_option_key(token)
    client = MockApiClient(token)
    
    print(f"--- Testing OPTION_GREEKS mode for {keys} ---")
    streamer = MarketDataStreamerV3(client, keys, mode="option_greeks")
    streamer.on("open", on_open)
    streamer.on("message", on_message)
    streamer.on("error", on_error)
    streamer.auto_reconnect(False)
    
    t = threading.Thread(target=streamer.connect, daemon=True)
    t.start()
    time.sleep(5)
    # streamer.disconnect() # Avoid clean disconnect issues
    print("Done.")

