import requests
import json
import sys
import pymysql
import hashlib
import base64
from cryptography.fernet import Fernet
import os
import asyncio
# Mocking instrument manager usage by direct DB or just simulating search results if possible.
# Since we can't easily import the full backend app context, we'll simulate the search by querying the Upstox API directly 
# to see what KEYS it returns for "HDFCBANK" and "BANKNIFTY".

# 1. Load SECRET_KEY
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
SECRET_KEY = "dev-secret-key-change-in-prod"
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r") as f:
        for line in f:
            if line.startswith("SECRET_KEY="):
                SECRET_KEY = line.strip().split("=", 1)[1].strip('"').strip("'")

def get_fernet():
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def decrypt(data):
    if not data: return ""
    f = get_fernet()
    if isinstance(data, memoryview): data = data.tobytes()
    return f.decrypt(data).decode()

# 2. Get Token
try:
    conn = pymysql.connect(host="localhost", user="root", password="Sai@1234", database="paper_trading")
    cursor = conn.cursor()
    cursor.execute("SELECT access_token FROM upstox_accounts WHERE status='TOKEN_VALID' LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if not row:
        print("No valid token")
        sys.exit(1)
    token = decrypt(row[0])
except Exception as e:
    print(f"DB Error: {e}")
    sys.exit(1)

headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}

def check_key(key):
    print(f"\n--- Checking Key: {key} ---")
    resp = requests.get("https://api.upstox.com/v2/market-quote/ltp", headers=headers, params={"instrument_key": key})
    print(f"LTP Status: {resp.status_code}")
    if resp.status_code == 200:
        print(json.dumps(resp.json(), indent=2))
    else:
        print(resp.text)

print("1. SEARCH for 'NIFTY 50'")
resp = requests.get("https://api.upstox.com/v2/market-quote/search/instrument", headers=headers, params={"instrument_key": "NSE_INDEX", "query": "NIFTY 50"})
if resp.status_code == 200:
    print("Search Result:", json.dumps(resp.json(), indent=2))

print("\n2. SEARCH for 'HDFCBANK'")
resp = requests.get("https://api.upstox.com/v2/market-quote/search/instrument", headers=headers, params={"instrument_key": "NSE_EQ", "query": "HDFCBANK"})
if resp.status_code == 200:
    print("Search Result:", json.dumps(resp.json(), indent=2))
    # Let's try to find the key we are likely using
    data = resp.json().get("data", [])
    if data:
        check_key(data[0]['instrument_key'])

print("\n3. SEARCH for 'BANKNIFTY'")
resp = requests.get("https://api.upstox.com/v2/market-quote/search/instrument", headers=headers, params={"instrument_key": "NSE_INDEX", "query": "BANKNIFTY"})
if resp.status_code == 200:
    print("Search Result:", json.dumps(resp.json(), indent=2))
    data = resp.json().get("data", [])
    if data:
        check_key(data[0]['instrument_key'])
        
print("\n4. Direct Check 'NSE_INDEX|Nifty Bank'")
check_key("NSE_INDEX|Nifty Bank")

print("\n5. Direct Check 'NSE_EQ|HDFCBANK' (Friendly Key?)")
check_key("NSE_EQ|HDFCBANK")
