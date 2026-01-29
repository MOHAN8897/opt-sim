# 🧪 TESTING GUIDE FOR CRITICAL FIXES

## Quick Test (2 minutes)

### Test #1: Live Ticks Appear ✅
1. Open browser DevTools (F12)
2. Go to "Network" tab
3. Reload trade page
4. **Expected**: Within 2-3 seconds, see WebSocket messages flowing
5. **Bad sign**: No messages after 10 seconds = deadlock not fixed

**What to look for in DevTools**:
```
WS Message Type: UPSTOX_FEED_CONNECTED (should appear within 2s)
WS Message Type: MARKET_UPDATE (should appear repeatedly)
```

---

### Test #2: OrderModal Shows Data ✅
1. On trade page, click on any option strike
2. **Expected**: Modal opens, shows Bid, Ask, LTP prices
3. **Bad sign**: Modal opens but all prices show 0 or "-"

**Visual check**:
```
Good ✅:
├─ Bid: 125.50
├─ Ask: 126.00
├─ LTP: 125.75
└─ Prices update every 1-2 seconds

Bad ❌:
├─ Bid: 0
├─ Ask: 0
├─ LTP: 0
└─ Numbers don't change
```

---

### Test #3: Refresh Persistence ✅
1. Select an option and open OrderModal
2. Press F5 to refresh
3. **Expected**: Modal still shows the selected option
4. **Bad sign**: Modal closes or shows blank after refresh

---

## Detailed Testing (10 minutes)

### Setup
- Open two windows: Browser DevTools + Backend Terminal logs
- Be ready to check both simultaneously

### Test Sequence

#### Step 1: Monitor Backend Logs
Open terminal and tail backend logs:
```bash
tail -f backend.log | grep -E "SWITCH|FEED_CONNECTED|MARKET_UPDATE"
```

**Expected output within 2 seconds**:
```
🔄 SWITCH UNDERLYING REQUEST: NSE_INDEX|Nifty 50 → NSE_INDEX|Nifty 50
📋 New session config: Spot Only (Auto-Expand on Tick)
🚀 Launching new feed session...
✅ UPSTOX FEED CONNECTED - Ready for data
📥 Received WebSocket data: 16 instruments
📤 Broadcasting 16 instruments
```

---

#### Step 2: Monitor Frontend Logs
Open Browser DevTools Console and look for:

**Expected**:
```
[useOptionChainData] 🔄 Switching to NSE_INDEX|Nifty 50 with 16 instruments
✅ Market WebSocket CONNECTED
```

**Bad signs**:
```
⏳ Waiting for feed to connect - BLOCKED (deadlock not fixed!)
Cannot switch underlying - WebSocket not connected (connection issue)
```

---

#### Step 3: Check Option Chain Updates
1. Look at option chain table on trade page
2. Watch for LTP column values
3. **Expected**: Values change every 1-2 seconds (you'll see them flashing/animating)
4. **Bad sign**: Values static for >10 seconds

---

#### Step 4: Test OrderModal
1. Click on a CALL option (not far OTM)
2. **Expected**: Modal opens immediately with live prices
3. **Verify**:
   - [ ] Bid price shows (not 0)
   - [ ] Ask price shows (not 0)
   - [ ] LTP shows (not 0)
   - [ ] Prices update every second (watch for animation)

---

#### Step 5: Test Persistence
1. Click on a PUT option (far OTM)
2. Leave modal open
3. Hit F5 to refresh page
4. **Expected**:
   - [ ] Page reloads
   - [ ] Modal stays open
   - [ ] Shows same selected option
   - [ ] Live prices still flow

---

#### Step 6: Test Multiple Instruments
1. Select different option (NIFTY 25000 CE instead of 24000 CE)
2. Check that modal updates
3. Verify prices are different
4. Refresh and verify it persists

---

## Automated Test Checklist

```
TEST COVERAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Fix #1: Deadlock - WebSocket subscriptions
  ├─ [ ] SWITCH UNDERLYING sent within 2 seconds
  ├─ [ ] FEED_CONNECTED received
  ├─ [ ] MARKET_UPDATE messages flowing
  └─ [ ] Live ticks in option chain updating

✅ Fix #2: Null guard - OrderModal safety
  ├─ [ ] Modal opens without crashing
  ├─ [ ] Modal shows live prices (not blank)
  ├─ [ ] Modal closes cleanly
  └─ [ ] No console errors about null selectedOption

✅ Fix #3: Persistence - localStorage
  ├─ [ ] Page refresh preserves selectedOption
  ├─ [ ] localStorage item exists (check DevTools → Application)
  ├─ [ ] Modal reopens with same selection
  └─ [ ] Clear localStorage and verify cleanup works

✅ Fix #4: App init - Store restoration
  ├─ [ ] StoreInitializer runs on mount
  ├─ [ ] selectedOption restored before routes render
  ├─ [ ] No race conditions with lazy loading
  └─ [ ] Works on initial page load (no navigation)

GENERAL CHECKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ├─ [ ] No console errors (F12 → Console tab)
  ├─ [ ] No console warnings about feedStatus
  ├─ [ ] Network shows WebSocket open
  ├─ [ ] All 16 strikes show live prices
  ├─ [ ] Prices animate/update continuously
  ├─ [ ] bid/ask spread is realistic (not 0)
  ├─ [ ] Backend logs show healthy data flow
  └─ [ ] No lag when clicking options
```

---

## Common Issues & Solutions

### Issue 1: Still showing "Waiting for feed to connect"
**Cause**: Old code still in place or cache issue  
**Solution**:
```bash
# Clear browser cache
rm -rf node_modules/.cache

# Hard refresh (Ctrl+Shift+R on Windows/Linux, Cmd+Shift+R on Mac)
```

---

### Issue 2: OrderModal still blank even with prices in chain
**Cause**: selectedOption not being persisted  
**Solution**:
1. Check UIStore has initializeFromLocalStorage method
2. Check App.tsx has StoreInitializer component
3. Clear localStorage: `localStorage.clear()` in console, reload

---

### Issue 3: localStorage not persisting
**Cause**: Private browsing mode or quota exceeded  
**Solution**:
1. Try normal (non-private) browsing
2. Check DevTools → Application → Storage → localStorage
3. Verify it shows: `uiStore_selectedOption` with JSON value

---

### Issue 4: MARKET_UPDATE messages only show 2-3 strikes
**Cause**: Subscription only partially successful  
**Solution**:
1. Check backend logs for full subscription list
2. Verify no truncation at 100 keys
3. Restart backend to reset feed session

---

## Performance Testing

### Latency Measurement
1. Open DevTools → Performance tab
2. Reload page
3. Record timeline
4. **Expected**:
   - [ ] SWITCH UNDERLYING sent: <2s
   - [ ] FEED_CONNECTED received: <5s
   - [ ] First MARKET_UPDATE: <6s
   - [ ] Option prices appear: <8s

### Memory Testing
1. Open DevTools → Memory tab
2. Take heap snapshot before test
3. Click option, open modal 5 times
4. Refresh 3 times
5. Take second heap snapshot
6. **Expected**: Memory growth <5MB

---

## Regression Testing

After fixes, verify nothing broke:

- [ ] Login flow still works
- [ ] Portfolio page loads
- [ ] Dashboard shows balances
- [ ] Account page accessible
- [ ] Other instruments work (BANKNIFTY, etc.)
- [ ] Greeks calculation if applicable
- [ ] Risk calculator if applicable
- [ ] Position closing works

---

## Sign-off Checklist

When all tests pass, confirm:

- [ ] Deadlock fixed - subscriptions happen immediately
- [ ] Null safety working - modal never goes blank
- [ ] Persistence working - state survives refresh
- [ ] No regressions - nothing else broke
- [ ] Performance good - no slowdowns
- [ ] Backend happy - logs look healthy
- [ ] User experience improved - trading workflow seamless

**Approved for Production**: ___________  
**Date**: ___________  
**Tester**: ___________

---

## Debugging Commands

If issues occur, use these to investigate:

### Browser Console
```javascript
// Check selectedOption in UI store
useUIStore.getState().selectedOption

// Check feedStatus in market store
useMarketStore.getState().feedStatus

// Check marketData
useMarketStore.getState().marketData

// Check localStorage
localStorage.getItem('uiStore_selectedOption')

// Clear and reset
localStorage.clear()
useUIStore.getState().closeOrderModal()
```

### Backend
```bash
# Show last 100 lines of logs
tail -100 backend.log

# Search for errors
grep ERROR backend.log | tail -20

# Search for subscription messages
grep "SWITCH\|FEED_" backend.log | tail -20

# Count MARKET_UPDATE messages per minute
grep MARKET_UPDATE backend.log | wc -l
```

---

**Testing Guide Complete** ✅  
Ready to validate fixes!
