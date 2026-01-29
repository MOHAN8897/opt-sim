import sys
import os
import pymysql
import hashlib
import base64
import json
import requests
from cryptography.fernet import Fernet
from datetime import datetime

# 1. Load SECRET_KEY
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
SECRET_KEY = None

if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r") as f:
        for line in f:
            if line.startswith("SECRET_KEY="):
                SECRET_KEY = line.strip().split("=", 1)[1].strip('"').strip("'")
                break

if not SECRET_KEY:
    print("SECRET_KEY not found in .env")
    sys.exit(1)

# 2. Decrypt Helper
def get_fernet():
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def decrypt(data):
    if not data: return ""
    f = get_fernet()
    # If using pymysql, binary data might be bytes or memoryview
    if isinstance(data, memoryview):
        data = data.tobytes()
    return f.decrypt(data).decode()

# 3. Get Token from DB (MySQL)
# DATABASE_URL=mysql+aiomysql://root:Sai%401234@localhost/paper_trading
try:
    conn = pymysql.connect(
        host="localhost",
        user="root",
        password="Sai@1234",
        database="paper_trading",
        port=3306
    )
    cursor = conn.cursor()

    # Get the first account with a token
    cursor.execute("SELECT access_token FROM upstox_accounts WHERE access_token IS NOT NULL LIMIT 1")
    row = cursor.fetchone()

    if not row:
        print("No logged in Upstox account found in DB.")
        sys.exit(1)

    encrypted_token = row[0]
    token = decrypt(encrypted_token)

    if not token:
        print("Failed to decrypt token.")
        sys.exit(1)

    print("Access Token retrieved successfully.")
    conn.close()

except Exception as e:
    print(f"Database Error: {e}")
    sys.exit(1)

# ... (Previous MySQL connection code remains) ...

# 4. Debug Logic
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

print("--- 1. Searching Instrument ---")
search_url = "https://api.upstox.com/v2/market-quote/search/instrument"
search_params = {"instrument_key": "NSE_INDEX", "query": "NIFTY 50"} 
# Or just "NIFTY"
# Documentation says: /market-quote/search/instrument?instrument_key=NSE_INDEX&query=blue...

# Wait, the search endpoint usually takes just 'query' and maybe 'exchange'.
# Let's check the URL I used in `backend/market_data.py` or just guess.
# Usually: https://api.upstox.com/v2/market-quote/search/instrument?instrument_key=... 
# Actually let's try just getting the metadata for a known key if search is complex.
# But searching is safer.

resp = requests.get(search_url, headers=headers, params={"instrument_key": "NSE_INDEX", "query": "NIFTY"})
if resp.status_code == 200:
    results = resp.json().get("data", [])
    # Find Nifty 50
    target = next((r for r in results if r.get("name") == "NIFTY 50" or r.get("trading_symbol") == "NIFTY 50"), None)
    if target:
        instrument_key = target["instrument_key"]
        print(f"Found Key: {instrument_key}")
    else:
        print("NIFTY 50 not found in search, using default.")
        instrument_key = "NSE_INDEX|Nifty 50"
else:
    print(f"Search failed: {resp.text}")
    instrument_key = "NSE_INDEX|Nifty 50"

print(f"Using Instrument Key: {instrument_key}")

print("--- 2. Fetching Expiry Dates ---")
# Endpoint checks?
# App uses: /option/contract?instrument_key=...
expiry_url = "https://api.upstox.com/v2/option/contract"
expiry_params = {"instrument_key": instrument_key}
resp = requests.get(expiry_url, headers=headers, params=expiry_params)
expiry_date = "2026-01-22"

if resp.status_code == 200:
    data = resp.json().get("data", [])
    if data:
        # data is list of objects with expiry
        # extract valid dates
        dates = sorted(list(set(d["expiry"] for d in data)))
        print(f"Available Expiries: {dates[:3]}...")
        if dates:
            expiry_date = dates[0]
            print(f"Selected Expiry: {expiry_date}")
else:
    print(f"Expiry fetch failed: {resp.text}")

print(f"--- 3. Fetching Option Chain for {instrument_key} exp {expiry_date} ---")

url = "https://api.upstox.com/v2/option/chain"
params = {
    "instrument_key": instrument_key,
    "expiry_date": expiry_date
}

resp = requests.get(url, headers=headers, params=params)
if resp.status_code != 200:
    print(f"Failed to fetch chain: {resp.text}")
    sys.exit(1)

data = resp.json().get("data", [])
print(f"Got {len(data)} rows in chain.")

if not data:
    sys.exit(0)

# Extract keys
keys_to_check = []
for row in data[:5]: # Take first 5
    # Both CE and PE
    if row.get("call_options"):
        keys_to_check.append(row["call_options"]["instrument_key"])
    if row.get("put_options"):
        keys_to_check.append(row["put_options"]["instrument_key"])

print(f"Checking keys: {keys_to_check}")

# Test LTP API
print("\n--- Testing LTP API ---")
ltp_url = "https://api.upstox.com/v2/market-quote/ltp"
ltp_params = {"instrument_key": ",".join(keys_to_check)}

ltp_resp = requests.get(ltp_url, headers=headers, params=ltp_params)
print(f"LTP Status: {ltp_resp.status_code}")
print(f"LTP Response: {json.dumps(ltp_resp.json(), indent=2)}")

# Test OHLC API
print("\n--- Testing OHLC API ---")
ohlc_url = "https://api.upstox.com/v2/market-quote/ohlc"
ohlc_params = {"instrument_key": ",".join(keys_to_check), "interval": "1d"}

ohlc_resp = requests.get(ohlc_url, headers=headers, params=ohlc_params)
print(f"OHLC Status: {ohlc_resp.status_code}")
print(f"OHLC Response: {json.dumps(ohlc_resp.json(), indent=2)}")

# Test Historical API
print("\n--- Testing Historical API ---")
if keys_to_check:
    key = keys_to_check[0]
    import urllib.parse
    encoded_key = urllib.parse.quote(key)
    # last few days
    hist_url = f"https://api.upstox.com/v2/historical-candle/{encoded_key}/1d/2026-01-18/2026-01-10"
    print(f"Hist URL: {hist_url}")
    hist_resp = requests.get(hist_url, headers=headers)
    print(f"Hist Status: {hist_resp.status_code}")
    # print(f"Hist Response: {hist_resp.text[:500]}")
