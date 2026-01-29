# Walkthrough: Performance Optimization Implementation

## Changes Overview

### Backend (`market_feed.py`)
1.  **Offloaded Greeks Calculation:** The expensive `calculate_greeks` function now runs in a `ThreadPoolExecutor` using `loop.run_in_executor`. This prevents the main async event loop from blocking.
2.  **Implemented Batching:** Introduced a `_broadcast_loop` that runs at ~5 FPS (0.2s interval). Updates are buffered and sent in a single JSON payload instead of one-per-tick.
3.  **Throttling:** Greeks are now recalculated at most once per second per instrument.
4.  **Broker V3 Optimization:** If the Upstox V3 feed provides Greeks/IV, we use them directly instead of recalculating (reducing CPU load).

### Frontend
1.  **Render Storm Fix (`OptionRow.tsx`):** The component no longer receives live data via props. Instead, it uses a new custom hook `useInstrumentData(key)` to subscribe only to the specific instrument it displays.
2.  **Referential Stability (`useOptionChainData.ts`):** The `staticChain` memo now strictly depends on the structure (strikes/keys) and is **not** invalidated by price updates.
3.  **Type Updates (`trading.ts`):** Made mutable fields like `iv`, `delta`, etc., optional in `OptionData` to better reflect the snapshot-vs-live data model.

## Verification

### How to Verify Locally
1.  **Start Backend:** Run `start-local-dev.bat`.
2.  **Connect:** Open the simulator in your browser.
3.  **Observe Logs:** You should see "Sending MARKET_UPDATE" logs roughly every 0.2s, containing a batch of instruments.
4.  **Observe UI:** The Option Chain should update smoothly. Using React DevTools "Highlight Updates", you should see only the specific cells flashing, not the entire table rows.
