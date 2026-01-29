import requests
from datetime import datetime
import time

# Use the same get_user_email and create_access_token from test_api_local.py
import sys
import pymysql
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "dev-secret-key-change-in-prod"
ALGORITHM = "HS256"
DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = "Sai@1234"
DB_NAME = "paper_trading"

def get_user_email():
    try:
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT u.email FROM users u JOIN upstox_accounts a ON u.id = a.user_id WHERE a.status = 'TOKEN_VALID' LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row: return row[0]
    except Exception as e:
        print(f"DB Error: {e}")
    return None

def create_access_token(email: str):
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode = {"sub": email, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def test_spot_price():
    email = get_user_email()
    if not email:
        print("No User with Valid Token found.")
        return

    print(f"Testing as user: {email}")
    token = create_access_token(email)
    headers = {"Authorization": f"Bearer {token}"}
    base_url = "http://127.0.0.1:8000/api/market"

    # Test NIFTY 50
    instrument_key = "NSE_INDEX|Nifty 50"
    print(f"\n--- Testing Spot Price for {instrument_key} ---")

    # 1. Get Expiry
    resp = requests.get(f"{base_url}/expiry", params={"instrument_key": instrument_key}, headers=headers)
    if resp.status_code != 200:
        print(f"Failed to get expiry: {resp.text}")
        return
    
    expiries = resp.json().get("expiry_dates", [])
    if not expiries:
        print("No expiries found.")
        return
    
    expiry = sorted(expiries)[0]
    print(f"Using Expiry: {expiry}")

    # 2. Get Option Chain (which includes spot price)
    print(f"Fetching Option Chain...")
    resp = requests.get(f"{base_url}/option-chain", params={"instrument_key": instrument_key, "expiry_date": expiry}, headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"Market Status: {data.get('market_status')}")
        print(f"Spot Price (Backend): {data.get('spot_price')}")
        print(f"ATM Strike: {data.get('atm_strike')}")
        
        # Verify Ltp endpoint directly
        print(f"\nFetching /ltp endpoint directly...")
        ltp_resp = requests.get(f"{base_url}/ltp", params={"instrument_key": instrument_key}, headers=headers)
        if ltp_resp.status_code == 200:
            ltp_data = ltp_resp.json()
            print(f"LTP Endpoint Response: {ltp_data}")
        else:
            print(f"LTP Endpoint Failed: {ltp_resp.status_code} {ltp_resp.text}")

    else:
        print(f"Option Chain Failed: {resp.status_code} {resp.text}")

if __name__ == "__main__":
    test_spot_price()
