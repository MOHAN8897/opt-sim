# Audit Report: Option Chain & Live Market Data

## Executive Summary
This audit focuses on the end-to-end flow of live market data (Ticks, OI, IV, Greeks) from the Upstox WebSocket to the Frontend Option Chain. 
**Critical bottlenecks** were found in both the Backend (blocking logic in async loops) and Frontend (inefficient re-rendering of the entire table).

---

## 1. Critical Backend Issues

### 🔴 1.1 Blocking Greeks Calculation (Major Latency Source)
**File:** `backend/market_feed.py`
**Severity:** Critical

*   **The Issue:** The `calculate_greeks` function is called synchronously inside the async `_process_data` loop for **every single tick** received.
*   **Why it's bad:** `calculate_greeks` imports `scipy.stats.norm` and uses `numpy`. These are CPU-bound, blocking operations. In Python's `asyncio` loop, a blocking call pauses the **entire** loop. No other packets can be processed, heartbeats might be missed, and latency accumulates rapidly during high volatility.
*   **Code Evidence:**
    ```python
    # backend/market_feed.py line 482
    greeks = calculate_greeks(self.spot_ltp, strike, ...) 
    ```
*   **Recommendation:** Offload Greeks calculation to a separate thread or process (using `run_in_executor`), or strictly throttle it to calculate only once per second per instrument.

### 🟠 1.2 Redundant IV Calculation
**File:** `backend/market_feed.py`
**Severity:** High

*   **The Issue:** The Upstox V3 Protobuf feed often provides pre-calculated IV and OI (in `fullFeed`). However, the backend logic recalculates Greeks (including iterative IV calculation via Newton-Raphson in `greeks_calculator.py`) without checking if the feed already provided valid values.
*   **Why it's bad:** Iterative root-finding for IV is computationally expensive (looping 100 times). Doing this when the broker already sent the data is wasteful.

### 🟡 1.3 Inefficient Object Creation
**File:** `backend/upstox_websocket_v3.py`
**Severity:** Medium

*   **The Issue:** `decode_market_data` instantiates a new `MarketDataFeedV3_pb2.FeedResponse()` and parses the entire binary string for every single message.
*   **Recommendation:** While protobuf parsing is necessary, the subsequent logic creates intermediate dictionaries for every single update, which generates significant garbage collection pressure.

---

## 2. Critical Frontend Issues

### 🔴 2.1 Infinite Re-render Loop (Render Storm)
**File:** `src/hooks/useOptionChainData.ts` & `src/components/trading/OptionRow.tsx`
**Severity:** Critical

*   **The Issue:**
    1.  `marketStore` receives an update and creates a new `greeksMap` object.
    2.  `useOptionChainData` has `greeksMap` in its dependency array.
    3.  When `greeksMap` changes (on every tick), `useMemo` runs and **re-creates the entire `staticChain` array**.
    4.  This means every row object in `staticChain` is a **new reference** (even if data didn't change).
    5.  `OptionRow.tsx` is wrapped in `React.memo`, but because the `row` prop is a new reference every time, **React.memo fails completely**.
*   **Impact:** If *one* instrument updates, **ALL 100+ rows** in the option chain re-render. This causes high CPU usage on the client and UI lag.
*   **Observation:** You will notice the UI freezing or stuttering during market hours.

### 🟠 2.2 Split Source of Truth
**File:** `src/components/trading/OptionRow.tsx`
**Severity:** Medium

*   **The Issue:** `OptionRow` reads LTP from `ltpMap` (direct store prop) BUT reads Greeks/IV from the `row` prop (passed from parent).
*   **Impact:** This makes optimization difficult. If we fix the `staticChain` regeneration issue, the `row` prop might become stale for Greeks, while LTP updates fine.

---

## 3. Data Flow Analysis & Bottlenecks

### Current Flow:
1.  **Upstox WS** sends Protobuf binary.
2.  **Backend (`upstox_websocket_v3`)** decodes to Dict.
3.  **Backend (`market_feed`)** blocks event loop to calculate Greeks. 🛑 **(Bottleneck)**
4.  **Backend (`socket_manager`)** JSON serializes huge payload.
5.  **Frontend (`marketStore`)** receives JSON, updates `greeksMap` (new object reference).
6.  **Frontend (`useOptionChainData`)** regenerates full `staticChain` array. 🛑 **(Bottleneck)**
7.  **Frontend (`OptionChainTable`)** passes new row objects to `OptionRow`.
8.  **Frontend (`OptionRow`)** re-renders indiscriminately. 🛑 **(Bottleneck)**

---

## 4. Recommendations for Immediate Fixes

### Backend Plan
1.  **Non-Blocking Greeks:** Move `calculate_greeks` to `loop.run_in_executor(None, ...)` to stop blocking the main async loop.
2.  **Throttle Greeks:** Only calculate Greeks if `last_calculation_time > 1 sec` for that instrument.
3.  **Trust Broker Data:** If `feed_data['iv'] > 0`, use it! Do not recalculate.

### Frontend Plan
1.  **Fix Memoization:** 
    *   Stop merging live data into `staticChain` inside the hook.
    *   Pass the *Key* (string) to `OptionRow`, not the full user object.
    *   Let `OptionRow` select its own data from `marketStore` (via a selector) or pass `greeksMap` down and let `OptionRow` look up its specific data.
    *   This ensures only the row that changed will re-render.

### Missing Data Handling
*   **IV/Greeks for Deep OTM:** The code currently returns 0s for failed calculations. We should ensure the UI handles these zeros gracefully (e.g., showing "-" instead of "0.00").
