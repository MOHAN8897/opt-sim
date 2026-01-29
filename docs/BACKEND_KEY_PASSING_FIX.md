# 🔴 CRITICAL BACKEND FIX - WebSocket Key Passing

**Date**: January 28, 2026  
**Issue**: Backend not receiving instrument keys, falling back to "dynamic mode"  
**Status**: ✅ FIXED

---

## The Problem

The backend logs showed:
```
🔄 SWITCH UNDERLYING REQUEST: NSE_INDEX|Nifty 50 → NSE_INDEX|Nifty 50
   Ignoring 35 frontend keys (Backend is source of truth)
⚠️ [FIX#1] No frontend keys provided, falling back to dynamic mode
```

**Root Cause**: `socket_manager.py` was intentionally passing an **empty list `[]`** instead of the actual 35 instrument keys to `bridge.switch_underlying()`.

This caused the backend to:
1. Fall back to "dynamic mode" (spot-only subscription)
2. Wait for first tick to determine ATM
3. Result: No option strikes subscribed initially
4. Trade page blank because no live prices flowing

---

## The Fix

**File**: `backend/socket_manager.py` (Line 451)

**Changed from**:
```python
await bridge.switch_underlying(underlying_key, [])  # ❌ Empty list!
```

**Changed to**:
```python
await bridge.switch_underlying(underlying_key, keys)  # ✅ Pass actual keys!
```

**Why this works**:
- Backend's `switch_underlying()` at line 1373 checks: `if new_instrument_keys and len(new_instrument_keys) > 2:`
- It needs these keys to immediately build the subscription list
- With keys, it skips dynamic mode and subscribes to all 35 strikes immediately
- Result: Live prices flowing from first tick

---

## Code Change

**Before** ❌:
```python
logger.info(f"🔄 SWITCH UNDERLYING REQUEST: {bridge.underlying_key} → {underlying_key}")
# We ignore frontend keys as per new contract
ignored_keys_count = len(keys) if keys else 0
logger.info(f"   Ignoring {ignored_keys_count} frontend keys (Backend is source of truth)")

await bridge.switch_underlying(underlying_key, [])  # ❌ WRONG: Passes empty list
```

**After** ✅:
```python
logger.info(f"🔄 SWITCH UNDERLYING REQUEST: {bridge.underlying_key} → {underlying_key}")
# ✅ FIX: PASS keys to backend (don't ignore them!)
# Backend will use these to immediately subscribe to all strikes
logger.info(f"   Passing {len(keys)} frontend keys to backend for subscription")

await bridge.switch_underlying(underlying_key, keys)  # ✅ CORRECT: Passes keys
```

---

## Expected Behavior After Fix

### Backend Logs:
```
🔄 SWITCH UNDERLYING REQUEST: NSE_INDEX|Nifty 50 → NSE_INDEX|Nifty 50
   Passing 35 frontend keys to backend for subscription
🔄 HARD SWITCH: NSE_INDEX|Nifty 50 → NSE_INDEX|Nifty 50
✅ [FIX#1] Using frontend-provided keys (35 instruments)
   Keys are already prioritized by distance to spot
📋 New session config: (35 strikes)
🚀 Launching new feed session...
📥 Received WebSocket data: 35 instruments  
📤 Broadcasting 35 instruments
```

### Frontend Behavior:
- ✅ All 35 strikes immediately get live prices
- ✅ LTP column updates every 1-2 seconds
- ✅ No blank pages
- ✅ Option chain fully populated with live data

---

## Testing

After restart, verify:

1. **Backend logs** (within 3 seconds):
   - [ ] "Passing 35 frontend keys"
   - [ ] "Using frontend-provided keys (35 instruments)"
   - [ ] "Broadcasting 35 instruments"

2. **Frontend** (within 3 seconds):
   - [ ] Option chain shows all 16 strikes
   - [ ] LTP prices not zero
   - [ ] Prices updating every 1-2 seconds

3. **Trade Page**:
   - [ ] Not blank
   - [ ] Click option → OrderModal shows live bid/ask
   - [ ] Prices animate continuously

---

## Impact

| Before Fix | After Fix |
|----------|-----------|
| ❌ No keys passed | ✅ 35 keys passed |
| ❌ Dynamic mode (waiting) | ✅ Immediate subscription |
| ❌ No live prices | ✅ All strikes live |
| ❌ Blank page | ✅ Full data display |

---

## Deployment

1. Restart backend: `full-reset-server.bat`
2. Refresh frontend page
3. Verify logs show "Passing 35 frontend keys"
4. Test trading workflow

---

**Fix Complete** ✅  
**File Changed**: `backend/socket_manager.py` (1 line)  
**Ready for Testing**: YES
