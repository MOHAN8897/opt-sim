"""
Quick diagnostic script to check broker token status and test API connectivity
"""
import requests
import json

# Test 1: Check if backend is reachable
print("="*70)
print("DIAGNOSTIC CHECKS FOR OPTION SIMULATOR")
print("="*70)
print()

backend_url = "http://localhost:8000"

try:
    print(f"[1/4] Testing Backend Connectivity ({backend_url})...")
    resp = requests.get(f"{backend_url}/docs", timeout=5)
    print(f"  ✅ Backend is UP (Status: {resp.status_code})")
except Exception as e:
    print(f"  ❌ Backend is DOWN: {e}")
    exit(1)

print()

# Test 2: Check broker status (requires auth)
print("[2/4] Checking if you're logged in...")
try:
    # Try to access a protected endpoint
    resp = requests.get(f"{backend_url}/api/broker/status", timeout=5)
    if resp.status_code == 401:
        print("  ⚠️  You need to log in first")
        print("  👉 Go to http://localhost:8080 and log in with Google")
    else:
        print(f"  Status Code: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"  Broker Status: {data.get('status', 'UNKNOWN')}")
            print(f"  Token Expiry: {data.get('token_expiry', 'N/A')}")
            print(f"  Feed Entitlement: {data.get('feed_entitlement', 'N/A')}")
except Exception as e:
    print(f"  ❌ Error: {e}")

print()

# Test 3: Check if Redis is working  
print("[3/4] Checking Redis...")
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    ping = r.ping()
    if ping:
        print("  ✅ Redis is UP")
    else:
        print("  ❌ Redis is DOWN")
except Exception as e:
    print(f"  ❌ Redis Error: {e}")

print()

# Test 4: Check WebSocket endpoint
print("[4/4] WebSocket Endpoint...")
print(f"  📍 WebSocket URL: ws://localhost:8000/ws/market-data")
print("  ℹ️  WebSocket connection requires auth cookie")
print()

print("="*70)
print("NEXT STEPS:")
print("="*70)
print("1. If backend is UP, go to http://localhost:8080")
print("2. Log in with Google")
print("3. Connect your Upstox broker account")
print("4. The option chain should show live data")
print()
