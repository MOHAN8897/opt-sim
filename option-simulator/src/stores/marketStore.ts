import { create } from "zustand";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

// Utility to generate or propagate correlation IDs for actions/events
function getCorrelationId(base?: string) {
  // Use a base (e.g., order ID) if provided, else random
  if (base) return base;
  return 'corr_' + Math.random().toString(36).slice(2) + Date.now();
}
import { useBrokerStore } from "./brokerStore";
import { BrokerStatus } from "@/types/trading";
import { toast } from "@/hooks/use-toast";

const STORE_NAME = "MarketStore";

// Throttle LTP logging to avoid console spam (log every 5 seconds per instrument)
const ltpLogThrottle = new Map<string, number>();
const LTP_LOG_INTERVAL = 5000; // 5 seconds

// ✅ NEW: Persistence helpers for market-closed scenario
const CACHE_KEY = "market_option_chain_cache";
const persistToLocalStorage = (chain: any) => {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({
      chain,
      timestamp: Date.now(),
      market_status: "CLOSED"
    }));
    logger.debug(STORE_NAME, "Option chain persisted to localStorage", undefined, getCorrelationId());
  } catch (e) {
    logger.warn(STORE_NAME, "Failed to persist to localStorage", e, getCorrelationId());
  }
};

const getFromLocalStorage = () => {
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached) {
      const data = JSON.parse(cached);
      // Only use cache if it's less than 24 hours old
      if (Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
        logger.debug(STORE_NAME, "Using cached option chain from localStorage", undefined, getCorrelationId());
        return data.chain;
      }
    }
  } catch (e) {
    logger.warn(STORE_NAME, "Failed to read from localStorage", e, getCorrelationId());
  }
  return null;
};

export interface OptionChainData {
  spot_price: number;
  chain: any[];
  atm_strike?: number;
  strike_step?: number;
  market_status?: string;
  // ✅ FIX: Inject request key to validate ownership
  instrument_key?: string;
}

export interface MarketData {
  ltp: number;
  volume: number; // Primary field name (backend sends 'volume')
  vol?: number; // DEPRECATED: Kept for backward compatibility
  oi: number; // Open Interest
  iv?: number;
  delta?: number;
  theta?: number;
  gamma?: number;
  vega?: number;
  lastUpdated?: number; // ✅ Phase 2: Heartbeat Timestamp
  seq?: number; // ✅ Phase 3: Sequence Number
  // ✅ NEW: Phase 1+2 - Bid/Ask data
  bid?: number;
  ask?: number;
  bid_qty?: number;
  ask_qty?: number;
  bid_ts?: number;
  ask_ts?: number;
  bid_simulated?: boolean;
  ask_simulated?: boolean;
  spread?: number;
  spread_pct?: number;
}


// ✅ Phase 2: Explicit Contracts
export interface FeedStateData {
  status: "LIVE" | "RESETTING" | "CLOSED";
  current_atm: number;
  status: "LIVE" | "RESETTING" | "CLOSED";
  current_atm: number;
  live_strikes: number[];
  version?: number; // ✅ Versioning
}

interface PendingSwitch {
  key: string;
  instruments: string[];
  expiryDate: string;
  timestamp: number;
  retryCount: number;
  maxRetries: number;
}

export interface FeedHealthData {
  state: string; // ✅ ADDED: State is present in payload
  active_keys: number;
  buffer_size: number;
  reset_locked: boolean;
  timestamp: string;
}

interface MarketState {
  ltpMap: Record<string, number>;
  previousLtpMap: Record<string, number>;
  marketData: Record<string, MarketData>; // Store full market data here
  netPnl: number;
  engineStatus: "RUNNING" | "PAUSED";
  optionChain: OptionChainData | null;
  isLoadingChain: boolean;
  searchResults: any[];
  expiryDates: string[];
  socket: WebSocket | null;

  // Feed status - Backend is SINGLE SOURCE OF TRUTH
  feedStatus: 'disconnected' | 'connecting' | 'connected' | 'unavailable' | 'market_closed';

  // Persistence & Queue
  selectedInstrument: { name: string; key: string } | null;
  selectedExpiryDate: string | null;
  pendingSubscriptions: string[];
  pendingUnderlying: PendingSwitch | null; // ✅ Robust Retry Queue
  activeInstruments: string[]; // Track currently subscribed keys
  liveStrikes: Set<number>; // ✅ O(1) Lookup for rendering

  // Actions
  setSelectedInstrument: (instrument: { name: string; key: string }) => void;
  setSelectedExpiryDate: (date: string) => void;
  updateLtp: (instrumentKey: string, ltp: number) => void;
  setNetPnl: (pnl: number) => void;
  setEngineStatus: (status: "RUNNING" | "PAUSED") => void;
  fetchOptionChain: (instrumentKey: string, expiryDate: string) => Promise<void>;
  searchInstruments: (query: string) => Promise<void>;
  fetchExpiryDates: (instrumentKey: string) => Promise<void>;
  reset: () => void;

  // WebSocket Actions
  connectWebSocket: (token: string) => void;
  disconnectWebSocket: () => void;
  switchUnderlying: (underlyingKey: string, instrumentKeys: string[]) => void;  // NEW: SESSION-BOUND
  // DEPRECATED: Use switchUnderlying instead
  subscribeToInstruments: (keys: string[]) => void;
  unsubscribeFromInstruments: (keys: string[]) => void;

  // Event Handlers
  handleMarketUpdate: (data: any) => void;
  handleBrokerError: (msg: string) => void;
  handleFeedConnected: () => void;
  handleFeedDisconnected: () => void;         // NEW
  handleFeedUnavailable: (msg: string) => void;
  handleMarketClosed: (msg: string) => void;  // NEW

  // ✅ Phase 2: New Handlers
  feedState: FeedStateData | null;
  feedHealth: FeedHealthData | null;
  handleFeedState: (data: FeedStateData) => void;
  handleFeedHealth: (data: FeedHealthData) => void;
  hasShownMarketClosedNotification: boolean; // ✅ NEW: Single toast per session
}

export const useMarketStore = create<MarketState>((set, get) => ({
  ltpMap: {},
  previousLtpMap: {},
  marketData: {},
  netPnl: 0,
  engineStatus: "RUNNING",
  optionChain: null,
  isLoadingChain: false,
  searchResults: [],
  expiryDates: [],
  socket: null,
  feedStatus: 'disconnected',  // NEW: Track feed readiness

  // ✅ FIX: Load from localStorage or default
  selectedInstrument: (() => {
    try {
      const saved = localStorage.getItem("selectedInstrument");
      return saved ? JSON.parse(saved) : { name: "NIFTY 50", key: "NSE_INDEX|Nifty 50" };
    } catch (e) {
      return { name: "NIFTY 50", key: "NSE_INDEX|Nifty 50" };
    }
  })(),

  selectedExpiryDate: null,
  pendingSubscriptions: [],
  pendingUnderlying: null, // ✅ Robust Retry Queue
  activeInstruments: [],
  liveStrikes: new Set(), // ✅ O(1)
  feedState: null, // ✅ Phase 2
  feedHealth: null, // ✅ Phase 2
  hasShownMarketClosedNotification: false, // ✅ NEW

  setSelectedInstrument: (instrument) => {
    try {
      localStorage.setItem("selectedInstrument", JSON.stringify(instrument));
    } catch (e) {
      console.warn("Failed to save instrument to localStorage");
    }
    set({ selectedInstrument: instrument });
  },
  setSelectedExpiryDate: (date) => set({ selectedExpiryDate: date }),

  connectWebSocket: (token: string) => {
    const { socket } = get();
    if (socket && socket.readyState === WebSocket.OPEN) {
      logger.info(STORE_NAME, "WebSocket already connected", undefined, getCorrelationId());
      return;
    }

    logger.info(STORE_NAME, "Connecting market websocket...", undefined, getCorrelationId());
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/market-data?token=${token}`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      logger.info(STORE_NAME, "✅ Market WebSocket CONNECTED", undefined, getCorrelationId());
      // Reset state on new connection (important for reconnection after fixing entitlement)
      set({
        feedStatus: 'connecting',  // Waiting for UPSTOX_FEED_CONNECTED
        pendingSubscriptions: []   // Clear old pending subs on fresh connection
      });
      // DO NOT subscribe here - wait for UPSTOX_FEED_CONNECTED event
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        // logger.debug(STORE_NAME, `WS Message Received: ${msg.type}`);

        // Backend is SINGLE SOURCE OF TRUTH for feed state
        if (msg.type === "UPSTOX_FEED_CONNECTED") {
          get().handleFeedConnected();
        } else if (msg.type === "UPSTOX_FEED_DISCONNECTED") {
          get().handleFeedDisconnected();
        } else if (msg.type === "MARKET_STATUS" && msg.status === "CLOSED") {
          get().handleMarketClosed(msg.msg);
        } else if (msg.type === "FEED_UNAVAILABLE") {
          get().handleFeedUnavailable(msg.msg);
        } else if (msg.type === "MARKET_UPDATE" && msg.data) {
          get().handleMarketUpdate(msg.data);
        } else if (msg.type === "ERROR" && msg.msg === "Broker Token Invalid") {
          get().handleBrokerError(msg.msg);
        } else if (msg.type === "FEED_STATE" && msg.data) { // ✅ Phase 2 - FIX: Guard msg.data
          get().handleFeedState(msg.data);
        } else if (msg.type === "FEED_HEALTH" && msg.data) { // ✅ Phase 2 - FIX: Guard msg.data
          get().handleFeedHealth(msg.data);
        } else if (msg.type === "SUBSCRIPTION_ACK") { // ✅ FIX Issue #9
          // console.log("[WS] Subscription ACK:", msg);
          // Optional: We could update a "loadingSubscription" state here
        }
      } catch (e) {
        logger.warn(STORE_NAME, `Failed to parse WebSocket message: ${e}`, undefined, getCorrelationId());
      }
    };

    ws.onclose = () => {
      logger.warn(STORE_NAME, "❌ Market WebSocket CLOSED", undefined, getCorrelationId());
      set({ socket: null, feedStatus: 'disconnected' });
    };

    ws.onerror = (error) => {
      logger.error(STORE_NAME, "WebSocket Error Event", error, getCorrelationId());
    };

    set({ socket: ws });
  },

  handleMarketUpdate: (data: any) => {
    // const instrumentCount = Object.keys(data).length;
    // logger.info(STORE_NAME, `Received MARKET_UPDATE for ${instrumentCount} instruments`);

    // Auto-promote status if we are receiving data (Fail-safe)
    const { feedStatus } = get();
    if (feedStatus === 'connecting') {
      console.log("[MarketStore] ⚠️ Auto-promoting feedStatus to 'connected' due to incoming data");
      set({ feedStatus: 'connected' });
    }

    // LOG 1: WS -> STORE (Baseline & Structure)
    const keys = Object.keys(data);
    const count = keys.length;

    // Throttle these logs slightly to avoid spamming 60fps
    if (count > 0 && Math.random() < 0.1) {
      console.groupCollapsed(`[WS→STORE] MARKET_UPDATE (${count} items)`);
      console.log("Raw Keys (Sample):", keys.slice(0, 5));

      const sampleKey = keys[0];
      const sampleVal = data[sampleKey];
      console.log("Structure Check (First Item):");
      console.log(`  Key: ${sampleKey}`);
      console.log("  Payload:", JSON.stringify(sampleVal, null, 2));

      // Explicit checks for "mapping and package"
      const hasLtp = sampleVal.ltp !== undefined;
      const hasVol = sampleVal.volume !== undefined || sampleVal.vol !== undefined;
      const hasOI = sampleVal.oi !== undefined;
      console.log(`  Fields Present: LTP=${hasLtp}, Vol=${hasVol}, OI=${hasOI}`);
      console.groupEnd();
    }

    set((state) => {
      const newLtpMap = { ...state.ltpMap };
      const newPrevMap = { ...state.previousLtpMap };

      // ✅ Correct Merge Strategy: Clone existing -> Merge updates
      const newMarketData = { ...state.marketData };

      Object.entries(data).forEach(([key, val]: [string, any]) => {
        // ✅ FIX: Robust Key Normalization (Handle both '|' and ':' separators)
        // If we receive "NSE_FO:..." but UI expects "NSE_FO|...", we ensure both exist in the store.
        const keysToUpdate = [key];
        if (key.includes(":")) keysToUpdate.push(key.replace(":", "|"));
        if (key.includes("|")) keysToUpdate.push(key.replace("|", ":"));

        keysToUpdate.forEach(k => {
          // 1. Update basic LTP maps (legacy/helper)
          if (val.ltp !== undefined) {
            if (state.ltpMap[k]) newPrevMap[k] = state.ltpMap[k];
            newLtpMap[k] = val.ltp; // Sync legacy map for fallback/initialization

            // Throttle logs
            const now = Date.now();
            const lastLog = ltpLogThrottle.get(k) || 0;
            if (now - lastLog > LTP_LOG_INTERVAL) {
              ltpLogThrottle.set(k, now);
            }
          }

          // 2. Update Master Market Data Record (Merging)
          const currentData: any = newMarketData[k] || {};

          // ✅ FIX: Normalize field names from backend (backend sends 'volume', store uses 'volume')
          const volumeFromBackend = val.volume ?? val.vol ?? 0; // Backend consistency

          // 🟢 PHASE 3: GAP DETECTION - FIX: Skip stale data early
          if (val.seq && currentData.seq) {
            if (val.seq <= currentData.seq) {
              console.warn(`[SEQ][GAP] ${k} Recv: ${val.seq} Cur: ${currentData.seq}`);
              // FIX: Skip updating with stale data - do not assign newMarketData[k]
              return;
            } else if (val.seq > currentData.seq + 1) {
              // console.debug(`[SEQ][SKIP] ${k} Dropped ${val.seq - currentData.seq - 1} ticks`);
            }
          }

          newMarketData[k] = {
            ...currentData, // Keep existing fields (like iv, delta) if not present in this update
            ltp: val.ltp ?? currentData.ltp ?? 0,
            volume: volumeFromBackend, // Store as 'volume' consistently
            vol: volumeFromBackend, // DEPRECATED: Keep for backward compatibility
            oi: val.oi ?? currentData.oi ?? 0,
            seq: val.seq, // ✅ Phase 3
            iv: val.iv ?? currentData.iv ?? 0, // Keep existing greeks if not in update

            delta: val.delta ?? currentData.delta ?? 0,
            theta: val.theta ?? currentData.theta ?? 0,
            gamma: val.gamma ?? currentData.gamma ?? 0,
            vega: val.vega ?? currentData.vega ?? 0,
            lastUpdated: Date.now(), // ✅ Phase 2: Heartbeat Timestamp
            // ✅ NEW: Phase 1+2 - Store bid/ask data
            bid: val.bid ?? currentData.bid,
            ask: val.ask ?? currentData.ask,
            bid_qty: val.bid_qty ?? currentData.bid_qty,
            ask_qty: val.ask_qty ?? currentData.ask_qty,
            bid_ts: val.bid_ts ?? currentData.bid_ts,
            ask_ts: val.ask_ts ?? currentData.ask_ts,
            bid_simulated: val.bid_simulated ?? currentData.bid_simulated,
            ask_simulated: val.ask_simulated ?? currentData.ask_simulated,
            spread: val.spread ?? currentData.spread,
            spread_pct: val.spread_pct ?? currentData.spread_pct,
          };
        });
      });

      // LOG 2: STORE UPDATE (Immutability Check + Greeks Verification)
      // LOG 2: STORE UPDATE (Immutability Check + Greeks Verification)
      const firstKey = Object.keys(data)[0];
      if (firstKey) {
        // We need to look up the NORMALIZED key because that's what we stored
        // The backend might send "NSE_FO:..." but we might have stored it as "NSE_FO|..." too
        // Let's just grab one of the normalized versions to check
        const normalizedKey = firstKey.includes(":") ? firstKey.replace(":", "|") : firstKey;
        const firstUpdated = newMarketData[normalizedKey] || newMarketData[firstKey];

        if (firstUpdated && Math.random() < 0.05) {
          console.log(
            "[STORE UPDATE]",
            {
              Key: normalizedKey,
              OldRef_vs_NewRef: state.marketData === newMarketData ? "SAME (❌ BUG!)" : "DIFFERENT (✅ GOOD)",
              New_LTP: firstUpdated?.ltp,
              New_Volume: firstUpdated?.volume,
              New_IV: firstUpdated?.iv,
              New_Delta: firstUpdated?.delta
            }
          );
        }
      }

      return {
        ltpMap: newLtpMap,
        previousLtpMap: newPrevMap,
        marketData: newMarketData
      };
    });
  },

  handleBrokerError: (msg: string) => {
    logger.error(STORE_NAME, `Broker Error: ${msg}`, undefined, getCorrelationId(msg));
    if (msg === "Broker Token Invalid") {
      const { setStatus } = useBrokerStore.getState();
      setStatus(BrokerStatus.TOKEN_EXPIRED);

      toast({
        title: "Broker Disconnected",
        description: "Your session with Upstox has expired. Please reconnect.",
        variant: "destructive",
      });
    }
  },

  handleFeedConnected: () => {
    logger.info(STORE_NAME, "✅ UPSTOX FEED CONNECTED - Ready for data", undefined, getCorrelationId());
    set({ feedStatus: 'connected' });

    // Flush pending subscriptions (initial setup only)
    const pending = get().pendingSubscriptions;
    const socket = get().socket;
    if (pending.length > 0 && socket && socket.readyState === WebSocket.OPEN) {
      logger.info(STORE_NAME, `Flushing ${pending.length} pending subscriptions...`, undefined, getCorrelationId());
      socket.send(JSON.stringify({ action: "subscribe", keys: pending }));
      set({ pendingSubscriptions: [] });
      socket.send(JSON.stringify({ action: "subscribe", keys: pending }));
      set({ pendingSubscriptions: [] });
    }

    // ✅ Process Pending Underlying Switch (Recovered from queue)
    const { pendingUnderlying, selectedExpiryDate, switchUnderlying } = get();
    if (pendingUnderlying) {
      // Validation 1: Expiry Match
      if (pendingUnderlying.expiryDate !== selectedExpiryDate) {
        logger.warn(STORE_NAME, "Queue invalidated: Expiry changed", { queued: pendingUnderlying.expiryDate, current: selectedExpiryDate });
        set({ pendingUnderlying: null });
        return;
      }

      // Validation 2: Stale Request (>15s)
      if (Date.now() - pendingUnderlying.timestamp > 15000) {
        logger.warn(STORE_NAME, "Queue invalidated: Request too old");
        set({ pendingUnderlying: null });
        return;
      }

      logger.info(STORE_NAME, `🚀 Retrying queued switch: ${pendingUnderlying.key}`);

      // Retry
      switchUnderlying(pendingUnderlying.key, pendingUnderlying.instruments);

      // Increment/Clear logic handled in switchUnderlying or here? 
      // Actually switchUnderlying handles the send. We just consume the queue.
      set({ pendingUnderlying: null });
    }
  },

  handleFeedDisconnected: () => {
    logger.warn(STORE_NAME, "❌ UPSTOX FEED DISCONNECTED");
    set({ feedStatus: 'disconnected' });
  },

  handleMarketClosed: (msg) => {
    // ✅ FIX: Debounce/Prevent duplicate toasts using persistent flag
    if (get().hasShownMarketClosedNotification) return;

    logger.warn(STORE_NAME, `⛔ MARKET CLOSED: ${msg}`);
    // We update status but DON'T reset the flag until a full hard reset
    set({ feedStatus: 'market_closed', hasShownMarketClosedNotification: true });

    toast({
      title: "Market Closed",
      description: msg || "Market is closed. Displaying REST API data only.",
      variant: "default",
      duration: 5000,
    });
  },

  handleFeedUnavailable: (msg: string) => {
    logger.error(STORE_NAME, `FEED UNAVAILABLE: ${msg}`);
    set({ feedStatus: 'unavailable' });

    toast({
      title: "Market Data Feed Unavailable",
      description: msg || "Market Data Feed permission not enabled in Upstox. Check Developer Console.",
      variant: "destructive",
      duration: 10000,
    });
  },

  // ✅ Phase 2: State Handlers
  handleFeedState: (data: FeedStateData) => {
    // Ensure live_strikes are always numbers
    const normalizedData = {
      ...data,
      live_strikes: data.live_strikes.map(s => Number(s))
    };
    if (normalizedData.status === "RESETTING") {
      logger.info(STORE_NAME, "⚠️ FEED RESETTING - Clearing Market Data");
      set({ feedState: normalizedData });
    } else {
      set({ feedState: normalizedData });
    }

    // ✅ Optimize: Create O(1) Set for rendering
    set({ liveStrikes: new Set(normalizedData.live_strikes) });
  },

  handleFeedHealth: (data: FeedHealthData) => {
    // High-frequency update, don't log
    set({ feedHealth: data });
  },

  disconnectWebSocket: () => {
    const { socket } = get();
    if (socket) {
      try { socket.close(); } catch (e) { console.error(e); }
      set({ socket: null, feedStatus: 'disconnected' });
    }
  },

  switchUnderlying: (underlyingKey: string, instrumentKeys: string[]) => {
    const { socket, feedStatus } = get();

    // 1. Queue if not ready
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      const { selectedExpiryDate } = get();
      logger.warn(STORE_NAME, "WebSocket not ready, queueing switch", { key: underlyingKey });

      set({
        pendingUnderlying: {
          key: underlyingKey,
          instruments: instrumentKeys,
          expiryDate: selectedExpiryDate || "",
          timestamp: Date.now(),
          retryCount: 0,
          maxRetries: 3
        }
      });
      return;
    }

    // 2. Validate Feed Status (unless forced via retry)
    if (feedStatus !== 'connected' && feedStatus !== 'connecting') {
      logger.warn(STORE_NAME, `⚠️ Cannot switch underlying - Feed status is '${feedStatus}'`);
      // We could queue here too?
      return;
    }

    logger.info(STORE_NAME, `🔄 SWITCH UNDERLYING: ${underlyingKey} (${instrumentKeys.length} instruments)`);

    // Send switch_underlying command to backend
    wsSend(socket, {
      action: "switch_underlying",
      underlying_key: underlyingKey,
      keys: instrumentKeys
    });

    // ✅ FIX #10: Clear old data to prevent ghost ticks
    set({
      activeInstruments: instrumentKeys,
      marketData: {},      // Clear rich market data
      ltpMap: {},          // Clear LTP map
      previousLtpMap: {}   // Clear history
    });
  },

  subscribeToInstruments: (keys: string[]) => {
    const { socket, feedStatus } = get();

    // DEPRECATED WARNING
    logger.warn(STORE_NAME, "⚠️ subscribeToInstruments() is DEPRECATED");
    logger.warn(STORE_NAME, "💡 Use switchUnderlying() instead for SESSION-BOUND mode");

    // For initial setup (before connection), allow it
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      logger.info(STORE_NAME, `📋 Deferring ${keys.length} subscriptions (initial setup)`);
      set((state) => ({
        pendingSubscriptions: Array.from(new Set([...state.pendingSubscriptions, ...keys]))
      }));
      return;
    }

    // If feed is connected, this should use switch_underlying instead
    if (feedStatus === 'connected') {
      logger.error(STORE_NAME, "❌ Cannot subscribe on active feed - use switchUnderlying()");
      return;
    }

    // Fallback for backward compatibility (initial subscribe)
    logger.info(STORE_NAME, `📋 Initial subscribe: ${keys.length} instruments`);
    wsSend(socket, { action: "subscribe", keys });
  },

  unsubscribeFromInstruments: (keys: string[]) => {
    // ❌ NOT SUPPORTED - Logs warning only
    logger.warn(STORE_NAME, `🚫 unsubscribe() called for ${keys.length} instruments`);
    logger.warn(STORE_NAME, "❌ NOT SUPPORTED in SESSION-BOUND mode");
    logger.warn(STORE_NAME, "📋 Request IGNORED - feed state unchanged");
    logger.warn(STORE_NAME, "💡 Use switchUnderlying() to change instruments");

    // DO NOT send to backend - it will ignore anyway
  },

  updateLtp: (instrumentKey, ltp) => {
    // Manual update if needed
    set((state) => {
      const previousLtp = state.ltpMap[instrumentKey] || ltp;
      return {
        previousLtpMap: { ...state.previousLtpMap, [instrumentKey]: previousLtp },
        ltpMap: { ...state.ltpMap, [instrumentKey]: ltp },
      };
    });
  },

  setNetPnl: (pnl) => {
    logger.info(STORE_NAME, `Net P&L updated: ₹${pnl.toFixed(2)}`);
    set({ netPnl: pnl });
  },

  setEngineStatus: (status) => {
    logger.info(STORE_NAME, `Engine status changed: ${status}`);
    set({ engineStatus: status });
  },

  fetchOptionChain: async (instrumentKey, expiryDate) => {
    const { isLoadingChain } = get();
    if (isLoadingChain) {
      logger.warn(STORE_NAME, "fetchOptionChain ignored - already loading");
      return;
    }
    set({ isLoadingChain: true });
    try {
      // Use the new endpoint
      const { data } = await api.get("/api/market/option-chain", {
        params: { instrument_key: instrumentKey, expiry_date: expiryDate }
      });

      logger.info(STORE_NAME, `Fetched Option Chain`, { count: data.chain.length, spot: data.spot_price, market_status: data.market_status });

      // ✅ SOLUTION 3: Validate response structure (Priority fields)
      const validationErrors = [];

      if (!data.chain || data.chain.length === 0) {
        validationErrors.push("⚠️ Empty chain from backend!");
        logger.error(STORE_NAME, "Empty chain received from backend");
      }

      if (!data.strike_step || data.strike_step === 0) {
        validationErrors.push("⚠️ Missing or zero strike_step from backend!");
        logger.error(STORE_NAME, "Missing/zero strike_step received");
      }

      if (!data.spot_price || data.spot_price === 0) {
        validationErrors.push("⚠️ Missing or zero spot_price from backend!");
        logger.warn(STORE_NAME, "Missing/zero spot_price - market likely closed or API failed");
      }

      // ✅ SOLUTION 3: Validate enrichment - check if LTP data is present
      if (data.chain && data.chain.length > 0) {
        const firstRow = data.chain[0];
        if (firstRow && firstRow.call_options) {
          if (!firstRow.call_options.ltp || firstRow.call_options.ltp === 0) {
            validationErrors.push("⚠️ Chain not enriched with LTP data!");
            logger.warn(STORE_NAME, "First row missing LTP data - enrichment may have failed", {
              strike: firstRow.strike_price,
              call_ltp: firstRow.call_options?.ltp,
              put_ltp: firstRow.put_options?.ltp
            });
          }
        }
      }

      // Log validation results
      if (validationErrors.length > 0) {
        logger.warn(STORE_NAME, "⚠️ Response Validation Issues:", validationErrors);
        console.warn("[marketStore] Full response:", data);
      } else {
        logger.info(STORE_NAME, "✅ Response validation passed");
      }

      // ✅ NEW: Log what we're storing
      logger.info(STORE_NAME, `✅ Option chain updated`, {
        spot_price: data.spot_price,
        market_status: data.market_status,
        chain_rows: data.chain?.length || 0,
        strike_step: data.strike_step,
        validation_issues: validationErrors.length
      });

      // ✅ NEW: Persist to localStorage for market-closed display
      persistToLocalStorage(data.chain);

      // ✅ FIX: Inject instrument_key into the stored object
      // This allows useOptionChainData to verify if the chain belongs to the selected instrument
      set({
        optionChain: {
          ...data,
          instrument_key: instrumentKey
        },
        isLoadingChain: false
      });
    } catch (error: any) {
      logger.error(STORE_NAME, 'Failed to fetch option chain', error);

      // ✅ CHECK FOR 401 UNAUTHORIZED (TOKEN EXPIRED)
      if (error.response?.status === 401) {
        logger.error(STORE_NAME, "Broker token expired - converting to TOKEN_EXPIRED status");
        get().handleBrokerError("Broker Token Invalid");
      }

      // ✅ NEW: On error, try to restore from cache for market-closed scenario
      const cachedChain = getFromLocalStorage();
      if (cachedChain) {
        logger.warn(STORE_NAME, "Using cached option chain data");
        set({
          optionChain: {
            spot_price: 0,  // Spot will be from API if available
            chain: cachedChain,
            market_status: "CLOSED"
          },
          isLoadingChain: false
        });
      } else {
        set({ isLoadingChain: false, optionChain: null });
      }
    }
  },

  searchInstruments: async (query) => {
    if (!query) {
      set({ searchResults: [] });
      return;
    }
    try {
      const { data } = await api.get("/api/market/search", { params: { query } });
      set({ searchResults: data });
    } catch (error: any) {
      logger.error(STORE_NAME, 'Search failed', error);

      // ✅ CHECK FOR 401 UNAUTHORIZED (TOKEN EXPIRED)
      if (error.response?.status === 401) {
        logger.error(STORE_NAME, "Broker token expired during search");
        get().handleBrokerError("Broker Token Invalid");
      }

      set({ searchResults: [] });
    }
  },

  fetchExpiryDates: async (instrumentKey) => {
    try {
      const { data } = await api.get("/api/market/expiry", { params: { instrument_key: instrumentKey } });
      set({ expiryDates: data.expiry_dates || [] });
    } catch (error: any) {
      logger.error(STORE_NAME, 'Fetch expiries failed', error);

      // ✅ CHECK FOR 401 UNAUTHORIZED (TOKEN EXPIRED)
      if (error.response?.status === 401) {
        logger.error(STORE_NAME, "Broker token expired during expiry fetch");
        get().handleBrokerError("Broker Token Invalid");
      }

      set({ expiryDates: [] });
    }
  },

  reset: () => {
    logger.info(STORE_NAME, 'Resetting market data');
    const { socket } = get();
    if (socket) socket.close();
    ltpLogThrottle.clear();
    set({
      ltpMap: {},
      previousLtpMap: {},
      marketData: {},
      netPnl: 0,
      engineStatus: "RUNNING",
      optionChain: null,
      searchResults: [],
      expiryDates: [],
      socket: null,
      feedStatus: 'disconnected',
      pendingSubscriptions: [],
      activeInstruments: []
    });
  },
}));

function wsSend(socket: WebSocket, msg: any) {
  try {
    socket.send(JSON.stringify(msg));
  } catch (e) { console.error("WS Send Error", e); }
}
