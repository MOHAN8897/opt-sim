# Walkthrough: Upstox Integration Fixes

## Solved Issues
1.  **Wrong Instrument Key:** `NSE_INDEX|Nifty 50` was failing to resolve because `instrument_manager` expected `NIFTY`. Fixed by updating the alias map to `Nifty 50`.
2.  **Auth 403 / Feed Entitlement:** The system was trying to reuse old authorized URLs or connect dynamically. Now, `restart_feed()` ensures a fresh authorized URL is generated for every connection attempt.
3.  **Dynamic Subscriptions:** Upstox V3 doesn't support dynamic `subscribe` on an open socket. We replaced `subscribe()` / `change_underlying` with a full `restart_feed()` cycle.
4.  **Market Closed Loops:** Added `is_market_open()` check. If market is closed, we log a warning and avoid aggressive retry loops.
5.  **Duplicate API Calls:** Added debounce to `fetchOptionChain` in frontend to prevent race conditions.
6.  **Feed Status Sync:** Frontend now waits for explicit `UPSTOX_FEED_CONNECTED` message before assuming connection is ready.

## Technical Details
- **`backend/market_feed.py`**:
    - Added `restart_feed(new_keys)`: Atomic Stop -> Auth -> Connect sequence.
    - Added `connect_lock`: `asyncio.Lock()` to prevent race conditions.
    - `subscribe()` now triggers `restart_feed`.
- **`backend/socket_manager.py`**:
    - Refactored `change_underlying` to use clean `restart_feed` logic.
- **`src/stores/marketStore.ts`**:
    - Added debounce to `fetchOptionChain`.

## Verification
1.  **Restart Server:** Run `full-reset-server.bat`.
2.  **Check Logs:**
    - Observe `[feed] Connection state: NOT_CONNECTED → CONNECTING`.
    - Observe `🔐 Calling WebSocket authorization endpoint...`.
    - Observe `✅ Authorization successful!`.
    - Observe `📡 Connecting to authorized WebSocket...`.
    - Finally `✅ WebSocket connected!`.
3.  **Change Instruments:** Select a different instrument or expiry.
    - Log should show `🔄 Restarting Market Data Feed...`.
    - Sequence repeats: Stop -> Auth -> Connect.
