# Issues Report

## 1. Partial Live Data (Only 11 Strikes Updating)
**Observation**: 11 strikes show live ticks, while the rest are static.
**Root Cause**:
- The frontend logic (`useOptionChainData.ts`) has a "Strict Mode" that filters the option chain to show *only* the strikes receiving live updates (`live_strikes`).
- This filtering is contingent on `isFeedLive` being true.
- Currently, it appears `isFeedLive` is evaluating to `false` (or `feedState` is not yet received/valid).
- **Result**: The frontend bypasses the filter and renders the **entire** option chain (all strikes).
- However, the backend (WebSocket) is likely only publishing ticks for a small "ATM Window" (e.g., 11 strikes).
- Thus, the user sees the full chain, but only the 11 subscribed strikes update; the rest remain static at their REST API snapshot values.

**Fix**:
1. Ensure `isFeedLive` correctly reflects the connection state.
2. If the intention is to validly show static rows for far-OTM strikes, this is "working as intended" but bad UX.
3. If the intention is to ONLY show live rows, we must ensure `isFeedLive` becomes true.
4. If the intention is to have MORE live rows, we need to check the backend subscription limit or increasing the window size.

## 2. Persistence Issues
**Observation 1**: Switching underlying fails.
**Observation 2**: Refreshing resets to "Nifty 50".
**Root Cause**:
- **Persistence**: `marketStore.ts` initializes `selectedInstrument` to a hardcoded default (`NSE_INDEX|Nifty 50`). There is no logic to read from `localStorage` or URL parameters on startup.
- **Switching**: The `switchUnderlying` function clears `marketData` and `ltpMap` but relies on the backend to confirm the switch. If the frontend doesn't gracefully handle the transition (e.g., `isLoading` state), the UI might blink or show empty state.

**Fix**:
1. **Persistence**: Implement `zustand/middleware/persist` or manual `localStorage` sync for `selectedInstrument`.
2. **Switching**: Ensure `isLoading` is set to true during the switch and verify the backend acknowledgment path.
