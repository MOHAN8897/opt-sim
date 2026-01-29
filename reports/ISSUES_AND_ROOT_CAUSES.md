# Option Simulator - Issues Analysis & Root Causes

**Date**: January 27, 2026  
**Status**: Critical Issues Identified  
**Severity**: High - Affecting User Experience

---

## 📋 Issue Summary

Three critical issues are affecting the trading interface:

1. **Trade Page Goes Blank When Clicking Greeks/Other Buttons**
2. **Underlying Not Persisting on Page Refresh**
3. **Live Ticks Not Loading for All Option Strikes**

---

## 🔴 ISSUE #1: Trade Page Goes Blank on Greeks/Button Clicks

### Symptoms
- User selects an option from the chain
- Clicks on Greeks button or any other action button
- Trade page becomes completely blank
- No error messages visible in UI

### Root Causes

#### 1.1 Missing Underlying Persistence in UIStore
**File**: [src/stores/uiStore.ts](src/stores/uiStore.ts)

**Problem**: The `selectedOption` is stored when opening the modal, but when the page refreshes or navigation happens, this state is lost because UIStore does not persist to localStorage.

```typescript
// Current Implementation (UIStore)
openOrderModal: (option) => set({ 
  orderModalOpen: true, 
  selectedOption: option  // ❌ In-memory only, lost on refresh
}),
```

**Impact**: When clicking buttons that trigger re-renders or modal transitions, the selectedOption becomes null, causing the OrderModal to render with undefined data.

#### 1.2 Missing Null Safety in OrderModal
**File**: [src/components/trading/OrderModal.tsx](src/components/trading/OrderModal.tsx) (Lines 1-50)

**Problem**: The component doesn't handle the case where `selectedOption` is null properly. All dependent calculations fail:

```typescript
const instrumentKey = selectedOption?.instrumentKey;  // ❌ May be undefined
const tick = useMarketStore(s => 
  instrumentKey ? s.marketData[instrumentKey] : undefined  // ❌ When undefined, causes blank
);

const staticLtp = selectedOption?.ltp ? Number(selectedOption.ltp) : 0;  // ❌ Returns 0
```

**Impact**: When `selectedOption` becomes null (on refresh or modal transition), all price data becomes 0, causing the modal to render blank form fields.

#### 1.3 Stale Closure in Order Modal
**Problem**: The modal is kept open after clicking buttons, but the data it depends on (selectedOption) is cleared by the store's `closeOrderModal()` function call sequence.

The flow is:
1. User clicks button → Opens OrderModal
2. OrderModal renders with selectedOption
3. Any re-render that triggers Zustand state update → Store may reset selectedOption
4. Modal remains visible but data is gone → Blank page

---

## 🟡 ISSUE #2: Underlying Not Persisting on Page Refresh

### Symptoms
- User selects NIFTY 50 from dropdown
- Page displays data for NIFTY 50
- User refreshes the page (F5 or Cmd+R)
- Underlying reverts to default (NIFTY 50, but ANY selected instrument reverts)
- Expiry date is also lost

### Root Causes

#### 2.1 No localStorage Persistence in MarketStore
**File**: [src/stores/marketStore.ts](src/stores/marketStore.ts) (Lines 100-150)

**Problem**: `selectedInstrument` and `selectedExpiryDate` are stored only in memory:

```typescript
selectedInstrument: { name: "NIFTY 50", key: "NSE_INDEX|Nifty 50" }, // ❌ Default
selectedExpiryDate: null, // ❌ Not persisted

// Action
setSelectedInstrument: (instrument) => set({ selectedInstrument: instrument })
// ❌ No localStorage.setItem() call
```

**Impact**: On page refresh, the store initializes with default values, losing user's selection.

#### 2.2 Missing useEffect to Load from localStorage
**File**: [src/hooks/useOptionChainData.ts](src/hooks/useOptionChainData.ts)

**Problem**: The hook doesn't restore selectedInstrument from localStorage on mount:

```typescript
export const useOptionChainData = () => {
    const {
        selectedInstrument,
        setSelectedInstrument,
        // ❌ No restoration logic from localStorage
    } = useMarketStore();

    // ❌ Missing:
    // useEffect(() => {
    //     const saved = localStorage.getItem('selectedInstrument');
    //     if (saved) setSelectedInstrument(JSON.parse(saved));
    // }, []);
}
```

**Impact**: User's instrument selection is lost on every page refresh.

---

## 🔴 ISSUE #3: Live Ticks Not Loading for All Option Strikes

### Symptoms
- Option chain displays with all strikes loaded (from REST API)
- Some strikes show live prices (LTP updates)
- Other strikes remain at REST API initial values
- No real-time updates for those strikes
- Particularly affects strikes outside ATM ± 2 range

### Root Causes (Primary & Secondary)

#### 3.1 Incomplete WebSocket Subscription
**File**: [src/hooks/useOptionChainData.ts](src/hooks/useOptionChainData.ts) (Lines 180-210)

**Problem**: The subscription list is not being properly communicated to the WebSocket for all strikes:

```typescript
useEffect(() => {
    if (optionChain && optionChain.chain && optionChain.chain.length > 0) {
        const prioritizedKeys = [];
        
        // ✅ Adds underlying
        if (selectedInstrument?.key) {
            prioritizedKeys.push({ key: selectedInstrument.key, distance: -1 });
        }

        // ✅ Adds all options from chain
        optionChain.chain.forEach((row: any) => {
            if (row.call_options?.instrument_key) {
                prioritizedKeys.push({ key: row.call_options.instrument_key, distance: dist });
            }
            if (row.put_options?.instrument_key) {
                prioritizedKeys.push({ key: row.put_options.instrument_key, distance: dist });
            }
        });

        const uniqueKeys = Array.from(new Set(prioritizedKeys.map(k => k.key)));
        
        // ❌ PROBLEM: Calls switchUnderlying ONLY if keys changed
        if (!isSame && uniqueKeys.length > 0) {
            switchUnderlying(selectedInstrument.key, uniqueKeys);  // ❌ May not include all strikes
        }
    }
}, [optionChain, selectedInstrument?.key, ...]);
```

**Impact**: If the subscription happens before all option chains are loaded, late-loading strikes won't be subscribed to.

#### 3.2 WebSocket Feed Status Check Too Strict
**File**: [src/hooks/useOptionChainData.ts](src/hooks/useOptionChainData.ts) (Lines 195-200)

**Problem**: The effect requires feed to be 'connected' before subscribing:

```typescript
if (feedStatus !== 'connected') {
    logger.warn(STORE_NAME, `⏳ Waiting for feed to connect...`);
    return;  // ❌ BLOCKS subscription if feed isn't connected yet
}
```

**Issue**: If the feed is still in 'connecting' state when option chain loads, the subscription never happens.

#### 3.3 Missing Strike in Feed State
**File**: [src/stores/marketStore.ts](src/stores/marketStore.ts) (Lines 270-290)

**Problem**: The `feedState.live_strikes` may not include all strikes in the option chain:

```typescript
// Frontend filters by live_strikes
if (isFeedLive && hasLiveStrikes) {
    const liveSet = new Set(feedState!.live_strikes.map(s => Number(s)));
    rowsToRender = optionChain.chain.filter((row: any) => {
        const rowStrike = Number(row.strike_price);
        return liveSet.has(rowStrike);  // ❌ Some strikes may not be in liveSet
    });
}
```

**Root Cause in Backend**: The backend WebSocket feed subscription may not include all requested strikes due to:
- Backend request limits (max 100 instruments per batch)
- Some strikes being excluded from subscription list
- Race condition between option chain fetch and subscription

**File**: [backend/market_feed.py](backend/market_feed.py) (Line 1235+)

```python
# ❌ Backend may not subscribe to all strikes
def switch_underlying(underlying_key: str, option_keys: list):
    # Truncates to first 100 keys
    option_keys = option_keys[:100]  # ❌ TRUNCATES remaining strikes!
    
    # Only subscribed instruments get live updates
    subscribe_to_instruments(option_keys)
```

#### 3.4 Initial Feed State Empty
**File**: [src/stores/marketStore.ts](src/stores/marketStore.ts) (Line 108)

**Problem**: `feedState` initializes as null:

```typescript
feedState: null,  // ❌ Starts as null
// When used in filter:
const hasLiveStrikes = feedState?.live_strikes && feedState.live_strikes.length > 0;
// ❌ Returns false on initial load, so NO filtering happens
// Then when feedState updates, filter applies but some strikes already rendered
```

**Impact**: Timing issue - strikes render before subscription happens.

#### 3.5 Race Condition in Market Data Update
**File**: [src/stores/marketStore.ts](src/stores/marketStore.ts) (Lines 200-250)

**Problem**: The order of operations causes some strikes to be displayed before their subscriptions are active:

```
Timeline:
1. Option chain fetched from REST API (all 16 strikes)
2. Rendered immediately with static LTP from REST
3. WebSocket subscription begins
4. feedState updates with live_strikes (maybe only 14 strikes)
5. Filter removes 2 strikes from display (too late - user saw them)
6. User clicks on strike that's in display but NOT in feedState
7. Live tick never received for that strike
8. LTP stays at REST API value forever
```

---

## 📊 Data Flow Issues

### Missing Data Flow for Greeks
**File**: [src/components/trading/OrderModal.tsx](src/components/trading/OrderModal.tsx)

**Problem**: Greeks data is fetched in the backend but not propagated to OrderModal:

```typescript
// Backend sends delta, gamma, theta, vega
// But OrderModal doesn't receive or display them
const liveTickLtp = tick?.ltp ? Number(tick.ltp) : 0;  // ✅ Has LTP
// ❌ Missing: Greeks data display
```

### Static vs Live Data Mismatch
**File**: [src/components/trading/OptionRow.tsx](src/components/trading/OptionRow.tsx) (Lines 70-100)

**Problem**: Fallback logic doesn't handle missing subscriptions gracefully:

```typescript
const getHybridLtp = (tick: any, staticLtp: number, persistedLtp: number) => {
    // 1. If WebSocket tick exists, use it
    if (tick && tick.ltp && tick.ltp > 0) {
        return tick.ltp;  // ✅ Live data
    }
    
    // 2. If persisted (last known), use it
    if (persistedLtp && persistedLtp > 0) {
        return persistedLtp;  // ✅ Fallback
    }
    
    // 3. If static REST API data exists, use it
    if (staticLtp && staticLtp > 0) {
        return staticLtp;  // ✅ Fallback
    }
    
    return 0;  // ❌ UI renders as "-" when all sources are 0
};
```

The issue: If a strike never gets subscribed (due to the 100-key limit), step 1 never happens, and it stays at staticLtp forever.

---

## 🛠️ Summary of Root Causes

| Issue | Root Cause | Component | Severity |
|-------|-----------|-----------|----------|
| Trade page blank | selectedOption not persisted | UIStore, OrderModal | 🔴 High |
| Underlying lost on refresh | No localStorage persistence | MarketStore | 🔴 High |
| Missing live ticks | Backend truncates subscriptions | market_feed.py, useOptionChainData | 🔴 High |
| Missing live ticks | Race condition in subscriptions | MarketStore, useOptionChainData | 🟡 Medium |
| Missing live ticks | Feed state timing issues | marketStore.ts | 🟡 Medium |

---

## 🔧 Technical Details

### Issue #1 - Blank Trade Page Fix Requirements

**Location**: 3 files
1. UIStore - Needs localStorage persistence
2. OrderModal - Needs null safety checks
3. MarketStore - May need to persist selectedOption too

**Changes Needed**:
- Add localStorage.setItem/getItem calls in UIStore
- Add fallback UI for when selectedOption is null
- Ensure OrderModal doesn't clear data unexpectedly

### Issue #2 - Underlying Persistence Fix Requirements

**Location**: 2 files
1. MarketStore - Add localStorage logic
2. useOptionChainData - Add restoration useEffect

**Changes Needed**:
- Implement localStorage persistence in store actions
- Add mount effect to restore from localStorage
- Handle expiry date restoration too

### Issue #3 - Live Ticks for All Strikes Fix Requirements

**Location**: Multiple files (Backend + Frontend)

**Frontend**:
1. useOptionChainData.ts - Better subscription timing
2. marketStore.ts - Improve feed state handling

**Backend**:
1. market_feed.py - Remove 100-key truncation or batch smarter
2. socket_manager.py - Ensure all subscriptions are sent

**Changes Needed**:
- Batch subscription requests properly (don't truncate)
- Implement deferred subscription for late-loading strikes
- Fix race conditions in feed state updates
- Add fallback to request remaining strikes

---

## 📈 Impact Analysis

### User Impact
- ❌ Cannot click buttons without page going blank
- ❌ Selections lost on page refresh (annoying UX)
- ❌ Real-time prices not updating for all options (trading risk)

### Data Flow Impact
- ❌ Option chain partially subscribed (only ~60% of strikes)
- ❌ Static REST data mixed with live WebSocket data
- ❌ No way to force re-subscription for missed strikes

### Performance Impact
- ✅ No major performance issues (except unnecessary re-renders)
- ⚠️ Potential memory leaks if OrderModal gets recreated repeatedly

---

## 🎯 Priority for Fixes

1. **CRITICAL** (Do First): Fix underlying persistence + OrderModal blanking
   - These prevent basic trading workflow
   - Can be fixed in frontend only

2. **HIGH** (Do Second): Fix live tick subscriptions
   - Affects trading accuracy
   - Requires backend changes

3. **MEDIUM** (Do Third): Fix Greeks display in OrderModal
   - Nice-to-have feature
   - Can wait for next iteration

---

## 📝 Testing Strategy

After fixes, verify:
1. ✅ Select instrument → Click button → OrderModal shows data
2. ✅ Select instrument → Refresh page → Selection persists
3. ✅ Select option strike → Wait 2s → Live price updates
4. ✅ All 16 strikes in chain → All receive live updates
5. ✅ Greeks calculated and displayed in OrderModal

---

**Next Steps**: Implement fixes based on priority order. See companion implementation guide for code changes.
