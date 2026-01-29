import asyncio
import logging
import httpx
import websockets
import sys
import os
import pymysql
import hashlib
import base64
from cryptography.fernet import Fernet

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("debug_ws")

# DB Config (from get_token.py)
DB_HOST = "localhost"
DB_USER = "root"
DB_PASS = "Sai@1234"
DB_NAME = "paper_trading"
SECRET_KEY = "dev-secret-key-change-in-prod"

def get_fernet():
    key = hashlib.sha256(SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def decrypt(encrypted_data: bytes) -> str:
    if not encrypted_data: return ""
    f = get_fernet()
    if isinstance(encrypted_data, str):
         # If stored as string but actually bytes-like
         return f.decrypt(encrypted_data.encode()).decode()
    return f.decrypt(encrypted_data).decode()

def get_token_from_db():
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        cursor = conn.cursor()
        cursor.execute("SELECT access_token FROM upstox_accounts WHERE status = 'TOKEN_VALID' ORDER BY updated_at DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return decrypt(row[0])
    except Exception as e:
        logger.error(f"Failed to fetch token from DB: {e}")
    return None

async def test_connection(access_token):
    if not access_token:
        logger.error("No access token provided or found.")
        return

    # 1. Authorize
    logger.info("Step 1: Authorizing...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.upstox.com/v3/feed/market-data-feed/authorize",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        )
        if resp.status_code != 200:
            logger.error(f"Auth failed: {resp.status_code} {resp.text}")
            return
        
        data = resp.json()
        if data['status'] != 'success':
            logger.error(f"Auth API error: {data}")
            return
            
        # We don't use this URL immediately, we get a new one for each attempt usually, 
        # but let's try to see if we can just use the auth flow successfully.
        logger.info(f"Auth Success! Got authorized_redirect_uri")

    # 2. Connect with various headers
    attempts = [
        {
            "desc": "Upstox Client UA (Production)", 
            "headers": {}, 
            "ua": "Upstox-Python-Client/3.0"
        },
        {
            "desc": "Baseline (No Headers)", 
            "headers": {}, 
            "ua": None
        }
    ]

    for attempt in attempts:
        logger.info(f"\n--- Testing: {attempt['desc']} ---")
        try:
            # Re-authorize for each attempt to get fresh single-use URL
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.upstox.com/v3/feed/market-data-feed/authorize",
                    headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
                )
                ws_url = resp.json()['data']['authorized_redirect_uri']

            logger.info("Connecting...")
            async with websockets.connect(
                ws_url,
                additional_headers=attempt['headers'],
                user_agent_header=attempt['ua'],
                open_timeout=10,
                ping_interval=None
            ) as ws:
                logger.info("✅ Connected successfully!")
                await ws.close()
                logger.info(f"🎉 SUCCESS! The configuration '{attempt['desc']}' works.")
                return # Stop after first success
                
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"❌ Connection rejected: {e.status_code}")
        except Exception as e:
            logger.error(f"❌ Error: {e}")

if __name__ == "__main__":
    token = get_token_from_db()
    if token:
        logger.info("Token retrieved from DB.")
        asyncio.run(test_connection(token))
    else:
        logger.error("Could not retrieve token.")
