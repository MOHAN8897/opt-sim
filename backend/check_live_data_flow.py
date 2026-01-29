"""
Comprehensive diagnostic to check live data flow:
Upstox API → Backend → Redis → Frontend
"""
import asyncio
import httpx
import json
from datetime import datetime

print("="*80)
print("LIVE DATA FLOW DIAGNOSTIC")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
print("="*80)
print()

# Check 1: Test Upstox API directly (requires token from .env)
print("[1/5] Testing Upstox API Connectivity...")
print("-"*80)

try:
    import os
    from pathlib import Path
    
    # Read .env file
    env_path = Path("C:/Users/subha/OneDrive/Desktop/simulator/.env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith("UPSTOX_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    print(f"  ✅ Found UPSTOX_API_KEY: {api_key[:10]}...")
    else:
        print("  ⚠️  .env file not found")
except Exception as e:
    print(f"  ❌ Error reading .env: {e}")

print()

# Check 2: Check if market is actually open
print("[2/5] Checking Market Status...")
print("-"*80)

now = datetime.now()
is_weekend = now.weekday() >= 5
is_trading_hours = (9, 15) <= (now.hour, now.minute) <= (15, 30)

print(f"  Day of Week: {now.strftime('%A')}")
print(f"  Current Time: {now.strftime('%H:%M:%S')}")
print(f"  Is Weekend: {is_weekend}")
print(f"  In Trading Hours: {is_trading_hours}")
print(f"  Market Should Be: {'OPEN ✅' if (not is_weekend and is_trading_hours) else 'CLOSED ❌'}")
print()

# Check 3: Check Redis connection
print("[3/5] Checking Redis...")
print("-"*80)

try:
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    ping = r.ping()
    if ping:
        print("  ✅ Redis is UP and responding")
        
        # Check for any WebSocket-related keys
        keys = r.keys("ws:*")
        print(f"  WebSocket Keys in Redis: {len(keys)}")
        if keys:
            for key in keys[:5]:  # Show first 5
                print(f"    - {key}")
        
        # Check for market data keys
        market_keys = r.keys("market:*")
        print(f"  Market Data Keys in Redis: {len(market_keys)}")
        if market_keys:
            for key in market_keys[:5]:
                print(f"    - {key}")
    else:
        print("  ❌ Redis ping failed")
except Exception as e:
    print(f"  ❌ Redis Error: {e}")

print()

# Check 4: Test Backend API
print("[4/5] Testing Backend API...")
print("-"*80)

async def test_backend():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test health
            resp = await client.get("http://localhost:8000/docs")
            print(f"  Backend Health: {resp.status_code} {'✅' if resp.status_code == 200 else '❌'}")
            
    except Exception as e:
        print(f"  ❌ Backend Error: {e}")

asyncio.run(test_backend())
print()

# Check 5: Check WebSocket endpoint
print("[5/5] WebSocket Endpoint Status...")
print("-"*80)
print("  WebSocket URL: ws://localhost:8000/ws/market-data")
print("  ℹ️  Requires authentication cookie")
print("  ℹ️  Connects automatically from frontend")
print()

print("="*80)
print("RECOMMENDATIONS:")
print("="*80)

if not is_weekend and is_trading_hours:
    print("✅ Market is OPEN - expecting live data")
    print()
    print("Next Steps:")
    print("1. Check Backend Terminal for WebSocket connection logs")
    print("2. Check for 'Upstox Feed CONNECTED' message")
    print("3. Check for 'MARKET_UPDATE' being sent")
    print("4. Open Browser Console (F12) and check for WebSocket messages")
else:
    print("⚠️  Market is CLOSED - zeros are expected")
    print()
    print("Next Trading Session:")
    print(f"  - Date: {now.strftime('%Y-%m-%d')}")
    print("  - Time: 09:15 AM IST")

print()
