import requests
import json
from datetime import datetime

# This script tests what the backend returns for option chain when market is closed

BASE_URL = "http://localhost:8000"

# You'll need to get a valid token from your Upstox account
# For testing, we can mock the response

print("=" * 80)
print("Testing Backend Option Chain Response")
print("=" * 80)

# Example parameters
params = {
    "instrument_key": "NSE_INDEX|Nifty 50",
    "expiry_date": "2025-02-27"  # Adjust to nearest expiry
}

print(f"\nEndpoint: {BASE_URL}/api/market/option-chain")
print(f"Params: {json.dumps(params, indent=2)}")
print(f"\nTime: {datetime.now()}")

print("\n" + "-" * 80)
print("What we EXPECT when market is CLOSED:")
print("-" * 80)

expected_response = {
    "spot_price": 24567.50,  # Should be populated from OHLC close price
    "chain": [
        {
            "strike_price": 24500,
            "is_atm": False,
            "call_options": {
                "instrument_key": "NSE_FO|NIFTY50JAN2524CP",
                "last_price": 150.50,
                "volume": 1000000,
                "open_interest": 2500000
            },
            "put_options": {
                "instrument_key": "NSE_FO|NIFTY50JAN2524PP",
                "last_price": 130.25,
                "volume": 950000,
                "open_interest": 2400000
            }
        }
    ],
    "atm_strike": 24550,
    "strike_step": 50,
    "market_status": "CLOSED"  # Market closed indicator
}

print(json.dumps(expected_response, indent=2))

print("\n" + "-" * 80)
print("Frontend Mapping:")
print("-" * 80)

frontend_code = """
// In useOptionChainData.ts line 205:
const currentSpotPrice = 
  (selectedInstrument && ltpMap[selectedInstrument.key]) ||  // Empty when market closed (no WS data)
  optionChain?.spot_price ||                                  // ✅ Should have 24567.50 from REST API
  0;

// ISSUE: If optionChain?.spot_price is NOT being set, then currentSpotPrice = 0

// The hook should receive optionChain from marketStore with spot_price:
optionChain = {
  spot_price: 24567.50,      // From backend response
  chain: [...],
  atm_strike: 24550,
  strike_step: 50,
  market_status: "CLOSED"
}

// Then OptionChain component gets it:
<motion.span key={currentSpotPrice}>
  {currentSpotPrice.toFixed(2)}  // Should display 24567.50
</motion.span>
"""

print(frontend_code)

print("\n" + "-" * 80)
print("Data Flow Chain (When Market Closed):")
print("-" * 80)

flow = """
1. User navigates to trade page (market closed)
   ↓
2. useOptionChainData hook runs
   - selectedInstrument = "NSE_INDEX|Nifty 50"
   - expiryDate = "2025-02-27"
   ↓
3. fetchOptionChain() called (marketStore action)
   ↓
4. Backend API /api/market/option-chain returns:
   {
     "spot_price": 24567.50,
     "chain": [...],
     "market_status": "CLOSED"
   }
   ↓
5. marketStore.set({ optionChain: data })
   ↓
6. useOptionChainData hook re-renders with new optionChain
   ↓
7. currentSpotPrice = optionChain?.spot_price = 24567.50
   ↓
8. OptionChain component receives currentSpotPrice = 24567.50
   ↓
9. <span key={24567.50}>{24567.50}</span> displays "Spot: 24567.50"
   ✅ SUCCESS

BUT IF optionChain?.spot_price is UNDEFINED:
   ↓
9. currentSpotPrice = 0
   ↓
10. <span>{0}</span> displays "Spot: 0.00"
    ❌ FAILURE
"""

print(flow)

print("\n" + "=" * 80)
print("DEBUGGING CHECKLIST")
print("=" * 80)

checklist = """
To find out why spot price is not showing:

1. ✅ Check Backend (this should be OK based on code review)
   - Start backend: cd backend && python main.py
   - Call: curl "http://localhost:8000/api/market/option-chain?instrument_key=NSE_INDEX%7CNifty%2050&expiry_date=2025-02-27"
   - Look for: "spot_price" field in response
   - Expected: "spot_price": 24567.50 (or similar number when market closed)

2. ⚠️ Check Frontend Store (marketStore receives data)
   - Open DevTools Console
   - Go to Redux DevTools (if installed)
   - Look at marketStore → optionChain
   - Check if optionChain.spot_price is populated

3. ⚠️ Check Hook (useOptionChainData computes correct value)
   - Look for new console log:
     "[useOptionChainData] Spot Price Calculation:"
   - Check what "computed currentSpotPrice" shows
   - Check if "optionChain?.spot_price" has value

4. ⚠️ Check Component (displays the value)
   - Look for rendered "Spot: XXX.XX"
   - Open React DevTools
   - Check <OptionChain> props: currentSpotPrice should have value

5. ⚠️ Check WebSocket Status (when market closed)
   - Look for "⛔ Market is CLOSED" in console
   - feedStatus should be "market_closed"
   - ltpMap should be empty {}

If spot_price IS in backend response BUT NOT showing in UI:
→ The issue is in the frontend data flow
→ Most likely: optionChain is not being updated in store
→ OR: Hook is not re-rendering when store updates
"""

print(checklist)

print("\n" + "=" * 80)
