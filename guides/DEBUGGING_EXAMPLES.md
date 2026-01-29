# 🔧 DEBUGGING EXAMPLES & TROUBLESHOOTING

## Real-World Scenarios

### Scenario 1: Option Chain Request During Market Hours (9:15-15:30 IST)

**What you click:** Frontend → Select NIFTY 50 → Get Option Chain

**Expected Log Output:**

```
════════════════════════════════════════════════════════════════════════════════════════
📥 [f7e8d9c0-b1a2-3c4d-5e6f-7g8h9i0j1k2l] GET /api/market/option-chain
════════════════════════════════════════════════════════════════════════════════════════
   Query params: {'instrument_key': 'NSE_INDEX|Nifty 50', 'expiry_date': '2024-01-25'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1: Determine Spot Price (for ATM calculation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ➊ PRIMARY: Trying /v3/market-quote/ltp (live endpoint)
✅ GET   200    11.2ms https://api.upstox.com/v3/market-quote/ltp
     ✅ PRIMARY: /market-quote/ltp → Spot price = 23450.50 (MARKET OPEN)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2: ATM Calculation & Chain Building
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Spot Price: 23450.50, Step Size: 100, ATM Strike: 23500
✅ Local chain built: 20 strike rows

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 3: Fetch Option Quote Data (LTP, Volume, OI, IV, Greeks)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📡 MARKET OPEN: Using /v3/market-quote/option-greek (includes Greeks)
   Fetching from: https://api.upstox.com/v3/market-quote/option-greek
   Total instruments: 40 (in 1 batches of 50)
   Market Status: OPEN
   ℹ️ OPEN MODE: Will return LIVE TRADING data
      - last_price: Live last traded price
      - volume: Today's accumulated volume
      - oi: Current open interest
      - iv: Implied Volatility (Greeks)

  Batch 1/1: 40 instruments
✅ GET   200   142.3ms https://api.upstox.com/v3/market-quote/option-greek [Batch 1/1]
  Batch 1: 40 quotes received

  ✅ CALL FOUND in quote_map: NSE_EQ|Nifty 50_2024-01-25_23500_CE
     LTP=145.25, Vol=5200, OI=125000, IV=0.2450, Delta=0.6234

✅ Quote fetch complete: 40/40 contracts received quote data

📦 ENRICHING CHAIN: 40 quotes available. Market Status: OPEN
   Sample keys in quote_map: ['NSE_EQ|Nifty 50_2024-01-25_23500_CE', ...]
🟢 MARKET OPEN MODE: Using live/current trading session data

════════════════════════════════════════════════════════════════════════════════════════
📤 [f7e8d9c0-b1a2-3c4d-5e6f-7g8h9i0j1k2l] ✅ 200 - 487.23ms
════════════════════════════════════════════════════════════════════════════════════════
```

**What's happening:**
1. ✅ Request enters backend
2. ✅ Spot price fetched successfully (23450.50)
3. ✅ ATM strike calculated (23500)
4. ✅ Local chain built (20 rows)
5. ✅ All 40 option quotes fetched with Greeks
6. ✅ Response sent back in 487ms
7. **Frontend shows:** Chain with live prices, Greeks, OI visible
8. **WebSocket:** Connects for live tick updates

---

### Scenario 2: Option Chain Request During Market Closed (After 15:30 IST)

**What you click:** Same as above, but after market hours

**Expected Log Output:**

```
════════════════════════════════════════════════════════════════════════════════════════
📥 [g8f9e0d1-c2b3-4d5e-6f7g-8h9i0j1k2l3m] GET /api/market/option-chain
════════════════════════════════════════════════════════════════════════════════════════

STEP 1: Determine Spot Price (for ATM calculation)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ➊ PRIMARY: Trying /v3/market-quote/ltp (live endpoint)
✅ GET   200    14.5ms https://api.upstox.com/v3/market-quote/ltp
     ⚠️ LTP returned 0 → Market likely CLOSED

  ➋ FALLBACK 1: /v2/market-quote/ohlc
✅ GET   200    17.8ms https://api.upstox.com/v2/market-quote/ohlc
     ✅ FALLBACK 1: /market-quote/ohlc → Spot price = 23420.00 (yesterday's close, MARKET CLOSED)

STEP 2: ATM Calculation & Chain Building
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Spot Price: 23420.00, Step Size: 100, ATM Strike: 23400
✅ Local chain built: 20 strike rows

STEP 3: Fetch Option Quote Data (LTP, Volume, OI, IV, Greeks)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📡 MARKET CLOSED: Using /v2/market-quote/full (persists last session prices)
   Fetching from: https://api.upstox.com/v2/market-quote/full
   Total instruments: 40 (in 1 batches of 50)
   Market Status: CLOSED
   ℹ️ CLOSED MODE: Will return LAST TRADING SESSION data
      - last_price: Last traded price from previous session
      - volume: Total volume from previous trading day
      - oi: Open interest from previous session

  Batch 1/1: 40 instruments
✅ GET   200   156.3ms https://api.upstox.com/v2/market-quote/full [Batch 1/1]
  Batch 1: 40 quotes received

  ✅ CALL FOUND in quote_map: NSE_EQ|Nifty 50_2024-01-25_23400_CE
     LTP=128.50, Vol=4850, OI=125000

✅ Quote fetch complete: 40/40 contracts received quote data

📦 ENRICHING CHAIN: 40 quotes available. Market Status: CLOSED
   Sample keys in quote_map: ['NSE_EQ|Nifty 50_2024-01-25_23400_CE', ...]
🔴 MARKET CLOSED MODE: Using last trading session data (previous close LTP, volume, OI)

════════════════════════════════════════════════════════════════════════════════════════
📤 [g8f9e0d1-c2b3-4d5e-6f7g-8h9i0j1k2l3m] ✅ 200 - 521.45ms
════════════════════════════════════════════════════════════════════════════════════════
```

**Key differences from market open:**
1. ⚠️ LTP returns 0 (expected when market closed)
2. Falls back to OHLC endpoint (yesterday's close)
3. Uses /v2/market-quote/full instead of /v3/option-greek
4. IV = 0, Greeks = 0 (no Greeks when market closed)
5. Shows previous session LTP/Volume/OI
6. **Frontend shows:** "Market Closed" badge + previous session prices
7. **WebSocket:** Doesn't update (market is closed)

---

### Scenario 3: Token Expiration (401 Error)

**What triggers it:** Token expired after last login

**Log output:**

```
════════════════════════════════════════════════════════════════════════════════════════
📥 [h9g0f1e2-d3c4-5e6f-7g8h-9i0j1k2l3m4n] GET /api/market/option-chain
════════════════════════════════════════════════════════════════════════════════════════

STEP 1: Determine Spot Price
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ➊ PRIMARY: Trying /v3/market-quote/ltp
❌ POST 401   128.5ms https://api.upstox.com/v3/market-quote/ltp
     ❌ 401 Unauthorized - Upstox token expired
     ❌ [auth] Token invalidation for user test@example.com (attempt 1)
     ✅ [auth] Database updated: Token marked as EXPIRED for test@example.com

════════════════════════════════════════════════════════════════════════════════════════
📤 [h9g0f1e2-d3c4-5e6f-7g8h-9i0j1k2l3m4n] ❌ 401 - 145.23ms
════════════════════════════════════════════════════════════════════════════════════════
```

**Frontend response:**
- Shows "Reconnect Broker" button
- Triggers OAuth flow again
- User needs to re-authenticate with Upstox

---

## 🆘 Troubleshooting

### Problem 1: "Quote fetch complete: 0/40 contracts received quote data"

**Logs show:**
```
✅ GET   200   156.3ms https://api.upstox.com/v2/market-quote/full
  Batch 1: 0 quotes received   ← PROBLEM!

✅ Quote fetch complete: 0/40 contracts received quote data
```

**Diagnosis:** API returned 200 (success) but no data in response

**Causes:**
1. **Empty response from API** - API returned `{"data": {}}`
2. **Wrong instrument keys** - Keys don't exist
3. **API issue** - Temporary problem with Upstox

**Solution:**
```bash
# Check if instrument keys are correct
cd backend
python debug_instruments.py

# Try fetching with curl to test API directly
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://api.upstox.com/v2/market-quote/full?instrument_key=NSE_EQ|Nifty50"
```

---

### Problem 2: "⚠️ LTP returned 0" but also not falling back to OHLC

**Logs show:**
```
✅ GET   200    12.3ms /v3/market-quote/ltp
     ⚠️ LTP returned 0 → Market likely CLOSED
  ⚠️ Spot Fetch Error
     ❌ Spot Price: 0, Step Size: 100, ATM Strike: 0
```

**Diagnosis:** All spot price methods failed

**Causes:**
1. **Token is invalid** - Should see 401 error
2. **All APIs are down** - Upstox having issues
3. **Connectivity** - Network unreachable

**Solution:**
```bash
# Test token validity
cd backend
python test_token_permissions.py

# Check if Upstox API is up
curl https://api.upstox.com/v2/market-quote/ltp \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "accept: application/json" \
  -G --data-urlencode "instrument_key=NSE_INDEX|Nifty 50"
```

---

### Problem 3: "Quote fetch complete: 38/40 contracts" (missing 2)

**Logs show:**
```
✅ Quote fetch complete: 38/40 contracts received quote data

  ❌ CALL NOT IN QUOTE_MAP: NSE_EQ|Nifty 50_2024-01-25_23700_CE
     Looking for key: NSE_EQ|Nifty 50_2024-01-25_23700_CE
     Available keys sample: ['NSE_EQ|Nifty 50_2024-01-25_23500_CE', ...]
```

**Diagnosis:** 2 options didn't get quotes (95% match)

**This is NORMAL!** Here's why:
- Far OTM options (edges of the chain) often have no quotes
- Bid-ask spread too wide = no trading
- Very low volume = not quoted

**No action needed:** Frontend will show zeros for these, which is fine

---

### Problem 4: "Market Status: UNKNOWN"

**Logs show:**
```
STEP 1: Determine Spot Price
⚠️ MARKET STATUS UNKNOWN - Using fallback endpoints
```

**Diagnosis:** Can't determine if market is open or closed

**Causes:**
1. **Between market hours** - e.g., 10:30 PM IST (between sessions)
2. **Weekend/Holiday** - Market doesn't open
3. **API issues** - Can't get reliable data

**Is it a problem?**
- If after 15:30 IST → Market is just closed, nothing to worry
- If between 9:15-15:30 IST → Might be a real issue

---

## 📊 Expected Values

### When Market is OPEN

```
Spot Price       : > 0 (e.g., 23450.50)
Endpoint         : /v3/market-quote/option-greek
Status Code      : 200
IV               : > 0 (e.g., 0.2450, 24.50%)
Delta            : Between -1 and 1 (e.g., 0.6234)
Volume           : Large (e.g., 5200, 15000)
OI               : Large (e.g., 125000)
Greeks Complete  : All 4 present (Delta, Gamma, Theta, Vega)
```

### When Market is CLOSED

```
Spot Price       : 0 initially, then falls back to yesterday's close
Endpoint         : /v2/market-quote/full (after fallback)
Status Code      : 200
IV               : 0 (no Greeks when market closed)
Delta            : 0
Gamma            : 0
Theta            : 0
Vega             : 0
Volume           : From previous day
OI               : From previous day
Greeks Complete  : All 0s (expected)
```

---

## 🚨 Critical Errors to Watch For

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Token expired | Click "Reconnect Broker" |
| `429 Too Many Requests` | Rate limit hit | Wait 60 seconds, try again |
| `500 Internal Server Error` | Upstox API down | Try again in 5 minutes |
| `404 Not Found` | Invalid endpoint/key | Check URL and instrument key |
| `InvalidInstrumentKeyError` | Wrong key format | Check instrument manager |
| Connection timeout | Network issue | Check internet, try again |

---

## 💻 Commands for Debugging

```bash
# Watch logs in real-time
cd backend
python monitor_logs.py

# View last 100 lines
python monitor_logs.py --tail 100

# Search for errors
python monitor_logs.py --search "ERROR"

# Search for 401 errors
python monitor_logs.py --search "401"

# View logs in PowerShell
Get-Content backend.log -Wait

# Save all errors to file
Select-String "ERROR" backend.log | Out-File errors.txt

# Count how many requests
Select-String "📥 ENTRY" backend.log | Measure-Object
```

---

## 🎓 Learning Flow

**If you want to understand the system:**

1. **Read:** COMPREHENSIVE_LOGGING_GUIDE.md
2. **Watch:** Run `monitor_logs.py` while clicking in frontend
3. **Test:** Try different scenarios:
   - During market hours
   - After market close
   - With invalid token
   - With rate limiting
4. **Experiment:** Modify logs in `logging_utils.py`
5. **Master:** Understand the complete flow from frontend → Upstox API

---

## ✅ Health Check Checklist

Run this checklist weekly:

- [ ] Backend starts without errors
- [ ] Option chain loads successfully (market hours)
- [ ] Option chain shows fallback prices (market closed)
- [ ] Greeks appear in logs when market open
- [ ] Greeks are zero when market closed
- [ ] Token validation works (401 triggers reconnect)
- [ ] WebSocket connects for live updates
- [ ] All logs have proper formatting
- [ ] No error logs in past 24 hours
- [ ] Response times are < 2 seconds

---

## 🎯 Next Steps

1. **Current:** You have logging enabled
2. **Next:** Monitor it during live trading
3. **Future:** Set up alerts for errors
4. **Advanced:** Export metrics to dashboard

---

## 📞 When in Doubt

If you see unexpected behavior:

1. **Check the logs first** - 90% of issues visible in logs
2. **Look for 📥/📤 markers** - See complete request flow
3. **Check status codes** - 401 = auth, 429 = rate limit, 500 = server
4. **Check market status** - Is market actually open?
5. **Check timestamp** - What time did error occur?
6. **Search for pattern** - Use grep to find similar errors

---

Good luck debugging! The logs will tell you everything you need to know! 🚀
