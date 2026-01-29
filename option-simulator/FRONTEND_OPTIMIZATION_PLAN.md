# Implementation Plan: Backend & Frontend Performance Optimization

## Goal
Optimize end-to-end latency for Option Chain and Live Market Data.

## Status
✅ **Backend:** Optimized `market_feed.py` with batching, threading, and smart Greek reuse.

## Phase 2: Frontend Optimization
**Goal:** Eliminate "Render Storm" where 100+ rows re-render on every tick.

### 1. `src/components/trading/OptionRow.tsx`
*   **Remove `columns` Prop:** It triggers re-renders if the object reference changes (even if content is same). Use a context or simpler prop.
*   **Change Data Subscription:** Do NOT pass the full `row` object (which contains live data and changes reference on every tick).
*   **Split Props:**
    *   Pass `staticData` (Strike, Instrument Keys, Option Type) - this NEVER changes.
    *   Pass `instrumentKey` explicitly.
*   **Internal Subscription:**
    *   Create a reusable hook `useInstrumentData(instrumentKey)` that selects *only* that instrument's data from the `marketStore`.
    *   `OptionRow` will use this hook for Call and Put keys.
    *   This ensures ONLY the row with the changing instrument re-renders.

### 2. `src/hooks/useOptionChainData.ts`
*   **Stop Merging:** Remove the logic that merges `live` data into the `staticChain`.
*   **Static Only:** `staticChain` should only contain the structural data (Strike prices, keys) derived from the initial API fetch. It should NOT depend on `greeksMap` or `ltpMap`.
*   **Dependency Cleanup:** Remove `greeksMap`, `ltpMap` from `useMemo` dependencies for `staticChain`.

### 3. `src/stores/marketStore.ts`
*   **Selector Optimization:** Ensure `useInstrumentData` uses a selector that compares values, not just references, or relies on Zustand's granular subscription.

## Detailed Steps

1.  **Modify `useOptionChainData`**:
    *   Change `staticChain` useMemo to strictly depend on `optionChain` (API response).
    *   Remove `getOptionData` merging logic.
    *   Return raw option keys/strikes.

2.  **Create `useInstrumentData` Hook**:
    ```typescript
    const useInstrumentData = (key: string) => {
      return useMarketStore(useShallow(state => state.greeksMap[key] || {}));
    };
    ```

3.  **Refactor `OptionRow`**:
    *   Accept `callKey`, `putKey`, `strike`, `isATM`.
    *   Call `useInstrumentData(callKey)` and `useInstrumentData(putKey)`.
    *   Render using these local values.

## Verification Plan
1.  **React DevTools:** Enable "Highlight updates". Only specific cells should flash, not the whole table.
2.  **Performance Profiler:** Check "Commit" times during volatility.
