# Implementation Plan: Backend Performance Optimization

## Goal
Optimize `backend/market_feed.py` to eliminate event loop blocking, reduce CPU usage, and improve WebSocket throughput.

## Proposed Changes

### 1. `backend/market_feed.py`

#### A. Architecture Change: Broadcast Loop
Introduce a "Producer-Consumer" pattern for WebSocket updates.
*   **Current:** `_process_data` (Producer) -> Direct Send (Consumer).
*   **New:** `_process_data` (Producer) -> Buffer -> `_broadcast_loop` (Consumer/Batcher).

#### B. Throttling and Offloading Greeks
Modify the Greeks calculation logic within `_process_data`:
1.  **Check Feed First:** If the incoming feed already contains non-zero IV/Greeks, use them directly.
2.  **Throttle:** Check if `last_calc_time` for this instrument was < 1 second ago. If so, skip calculation (reuse last known or send partial update).
3.  **Offload:** If calculation is needed, use `loop.run_in_executor` to run `calculate_greeks` in a thread pool, preventing it from blocking the main async loop.

#### C. Batching Updates
*   Create a `self.update_buffer` dictionary.
*   `_process_data` updates this buffer (merging latest values for each instrument).
*   `_broadcast_loop` runs every 200ms (configurable), flushes the buffer, and sends a single coalesced JSON message to the frontend.

## Detailed Flow

### `UpstoxFeedBridge` Class Updates

1.  **`__init__`**:
    *   Initialize `self.update_buffer = {}`.
    *   Initialize `self.last_greeks_calc = {}`.
    *   Initialize `self.broadcast_task = None`.

2.  **`connect_and_run`**:
    *   Start `self.broadcast_task = asyncio.create_task(self._broadcast_loop())`.

3.  **Stop Logic**:
    *   Cancel `self.broadcast_task` in `stop()`.

4.  **`_broadcast_loop`**:
    ```python
    async def _broadcast_loop(self):
        while self.keep_running:
            await asyncio.sleep(0.2) # 5 FPS is sufficient for tabular data
            if self.update_buffer:
                # Swap buffer to ensure atomic-like flush
                chk = self.update_buffer
                self.update_buffer = {}
                await self.send_to_frontend(chk)
    ```

5.  **`_process_data` Logic**:
    ```python
    # ... inside loop ...
    if has_broker_iv:
        data.update(broker_greeks)
    elif should_calculate_greeks(key):
        # Run in thread
        greeks = await loop.run_in_executor(None, calculate_greeks, ...)
        data.update(greeks)
        self.last_greeks_calc[key] = now
    
    self.update_buffer[key] = data
    ```

## Verification Plan
1.  **Latency Check:** Observe logs for "WS Message Received" vs "Sending MARKET_UPDATE".
2.  **CPU Usage:** Backend process should consume significantly less CPU during volatility.
3.  **UI Fluidity:** Frontend should receive updates in chunks rather than a stream of single-row updates (though the frontend fix is also needed for full smoothness).
