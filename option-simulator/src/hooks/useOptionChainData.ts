import { useState, useEffect, useMemo, useCallback } from "react";
import { useMarketStore } from "@/stores/marketStore";
import { useBrokerStore } from "@/stores/brokerStore";
import { BrokerStatus, OptionChainRow, OptionData } from "@/types/trading";
import { logger } from "@/lib/logger";

const STORE_NAME = "useOptionChainData";

export const useOptionChainData = () => {
    // Remove local state, use Store state
    const {
        selectedInstrument,
        selectedExpiryDate: expiryDate, // Aliasing for compatibility
        setSelectedInstrument,
        setSelectedExpiryDate: setExpiryDate,
        ltpMap,
        previousLtpMap,
        marketData,
        engineStatus,
        optionChain,
        fetchOptionChain,
        isLoadingChain,
        searchResults,
        searchInstruments,
        expiryDates,
        fetchExpiryDates,
        connectWebSocket,
        disconnectWebSocket,
        switchUnderlying,  // Use switchUnderlying instead of subscribe/unsubscribe
        feedStatus,  // NEW: Track feed readiness
        activeInstruments,
        feedState, // ✅ ADDED: Needed for filtering
        liveStrikes, // ✅ ADDED: O(1) Set
        feedHealth // ✅ ADDED: Needed for status override
    } = useMarketStore();

    // UI State for Search (local is fine)
    const [searchQuery, setSearchQuery] = useState("");
    const [isSearchOpen, setIsSearchOpen] = useState(false);
    const [activeKeys, setActiveKeys] = useState<string[]>([]);
    const [wsToken, setWsToken] = useState<string | null>(null);

    const { status: brokerStatus } = useBrokerStore();

    // 🔴 CRITICAL FIX: Defined BEFORE useMemo so it can be used for filtering
    // When market is CLOSED, use REST API spot_price (more reliable)
    // When market is OPEN, use WebSocket ltpMap for live updates
    const marketStatus = optionChain?.market_status || "OPEN";

    // Computed Values
    // Fail-safe Spot Price Logic
    // Problem: Sometimes WebSocket sends an option price (e.g. 100) for the Spot Index (e.g. 23000)
    // Solution: Validate WS price against REST API snapshot. If invalid, fallback to REST.
    const currentSpotPrice = useMemo(() => {
        const restSpot = optionChain?.spot_price || 0;

        // Try to get live spot from ltpMap
        // Try to get live spot from marketData (Rich Store) or ltpMap (Primitive Fallback)
        let liveSpot = 0;
        const key = selectedInstrument?.key;

        if (key) {
            // Priority 1: Market Data (Rich Object)
            if (marketData[key]?.ltp) {
                liveSpot = Number(marketData[key].ltp);
            }
            // Priority 2: LTP Map (Primitive) - Check if it exists and is not 0
            else if (ltpMap[key]) {
                liveSpot = Number(ltpMap[key]);
            }
            // Priority 3: Previous LTP Map (Persistence)
            else if (previousLtpMap[key]) {
                liveSpot = Number(previousLtpMap[key]);
            }
        }

        // Debug
        // console.log(`[SpotCalc] REST=${restSpot} LIVE=${liveSpot} STATUS=${marketStatus}`);

        // 1. If Market is CLOSED, always trust REST API
        if (marketStatus === "CLOSED") return restSpot > 0 ? restSpot : liveSpot;

        // 2. If no live data, use REST
        if (!liveSpot || liveSpot === 0) return restSpot;

        // 3. VALIDATION: Check for massive deviation (e.g. > 20%)
        if (restSpot > 0) {
            const deviation = Math.abs(liveSpot - restSpot) / restSpot;
            if (deviation > 0.2) {
                return restSpot;
            }
        }

        return liveSpot;
    }, [selectedInstrument, ltpMap, optionChain?.spot_price, marketStatus, marketData, previousLtpMap]);

    // Fetch Token for WebSocket (Fixes HttpOnly cookie issue)
    useEffect(() => {
        let mounted = true;
        const fetchToken = async () => {
            try {
                // We need to import api here to avoid circular dep if defined outside
                // But imports are top-level.
                const { api } = await import("@/lib/api");
                const { data } = await api.get("/api/auth/token");
                if (mounted && data.access_token) {
                    setWsToken(data.access_token);
                }
            } catch (e) {
                logger.warn(STORE_NAME, "Failed to fetch WS token", e);
            }
        };
        fetchToken();
        return () => { mounted = false; };
    }, []);

    // Connect WebSocket on Mount (once token is available)
    useEffect(() => {
        if (wsToken) {
            connectWebSocket(wsToken);
        }
        return () => {
            disconnectWebSocket();
        };
    }, [connectWebSocket, disconnectWebSocket, wsToken]);

    // Reset expiry on instrument change
    useEffect(() => {
        // Only reset if expiry doesn't match available dates for new instrument?
        // Or just clear it. 
        // Store logic defaults to null, we can keep it or clear it.
        // For now, let's clear it if the key changes to force re-selection or auto-select
        setExpiryDate("");
    }, [selectedInstrument?.key, setExpiryDate]);

    // Manage Subscriptions
    useEffect(() => {
        if (optionChain && optionChain.chain && optionChain.chain.length > 0) {
            // ✅ FIX: Sort keys by proximity to Spot Price (ATM)
            // This ensures that when backend limits to 100 keys, we keep the most relevant ones.
            const spot = currentSpotPrice || optionChain.spot_price || 0;

            const prioritizedKeys: { key: string, distance: number }[] = [];

            // Always subscribe to underlying spot price (Priority #1 - Distance -1)
            if (selectedInstrument?.key) {
                prioritizedKeys.push({ key: selectedInstrument.key, distance: -1 });
            }

            optionChain.chain.forEach((row: any) => {
                const dist = Math.abs(row.strike_price - spot);
                if (row.call_options?.instrument_key) {
                    prioritizedKeys.push({ key: row.call_options.instrument_key, distance: dist });
                }
                if (row.put_options?.instrument_key) {
                    prioritizedKeys.push({ key: row.put_options.instrument_key, distance: dist });
                }
            });

            // Sort: Underlying first (-1), then closest strikes
            prioritizedKeys.sort((a, b) => a.distance - b.distance);

            // Extract sorted keys
            const uniqueKeys = Array.from(new Set(prioritizedKeys.map(k => k.key)));

            // Compare with activeKeys (simple length check + every check)
            const isSame = activeKeys.length === uniqueKeys.length && activeKeys.every((k) => uniqueKeys.includes(k));

            if (!isSame && uniqueKeys.length > 0) {
                // 🚨 CRITICAL: Only switch if feed is in good state (allow 'connecting' since socket is physically open)
                // FIX: Changed from feedStatus !== 'connected' to only blocking bad states
                // Reason: WebSocket is physically OPEN in 'connecting' state and CAN receive messages
                // The old logic created a deadlock: Frontend waits for 'connected', but backend sends 'connected'
                // AFTER receiving the subscription request. We need to allow 'connecting' state.
                if (feedStatus === 'disconnected' || feedStatus === 'unavailable' || feedStatus === 'market_closed') {
                    logger.warn(STORE_NAME, `⏳ Cannot switch - feed status is '${feedStatus}' - waiting for feed to become available`);
                    return;
                }

                // FIX: Split-Brain Prevention
                // Verify that the option chain we calculated keys for matches the CURRENTLY selected instrument.
                // If the user switched instruments while fetchOptionChain was in flight, this effect might run with old data.

                // We primarily rely on the uniqueKeys check below, but we can also check if the active instrument matches.
                if (selectedInstrument?.key) {
                    // Note: backend response doesn't always have instrument_key in root. 
                    // But we can check if the underlying key of the chain rows matches our expectation?
                    // Actually, a simpler check is: The Effect dependency [selectedInstrument?.key] handles re-runs.
                    // The Race Condition happens in `fetchOptionChain` (async).
                    // But THIS effect runs on `optionChain` update.
                    // If `fetchOptionChain` updates `optionChain` in the store, and that `optionChain` belongs to "NIFTY",
                    // but `selectedInstrument` is now "BANKNIFTY", we have a mismatch.

                    // We need to ensure the optionChain we accept really belongs to the selectedInstrument.
                    // IMPORTANT: The backend `fetchOptionChain` response needs to propagate which instrument it was for,
                    // OR we rely on the fact that `optionChain` store update should be atomic with `selectedInstrument` check?
                    // No, `fetchOptionChain` just sets `optionChain`.

                    // Let's rely on the Request ID pattern in the store action, OR 
                    // Check if `uniqueKeys` contains the `selectedInstrument.key` (since we added it at distance -1).

                    // ✅ FIX Issue #1: Robust Race Condition Check
                    // Verify if the active OptionChain belongs to the selected instrument
                    // using the injected 'instrument_key' field.
                    if (optionChain.instrument_key && optionChain.instrument_key !== selectedInstrument.key) {
                        logger.warn(STORE_NAME, `⚠️ RACE DETECTED: Chain for ${optionChain.instrument_key} but selected is ${selectedInstrument.key}. Aborting subscription.`);
                        return;
                    }
                }

                // SESSION-BOUND MODE: Use switchUnderlying instead of subscribe/unsubscribe
                if (selectedInstrument?.key) {
                    logger.info(STORE_NAME, `🔄 Switching to ${selectedInstrument.key} with ${uniqueKeys.length} instruments (Rows: ${optionChain.chain.length}, Spot: ${spot})`);
                    console.log("[useOptionChainData] Subscription List Priority Sample:", uniqueKeys.slice(0, 5));
                    switchUnderlying(selectedInstrument.key, uniqueKeys);
                    setActiveKeys(uniqueKeys);
                }
            }
        }
    }, [optionChain, selectedInstrument?.key, activeKeys, switchUnderlying, feedStatus]);

    // Debounce Search
    useEffect(() => {
        if (!isSearchOpen) return;
        const timer = setTimeout(() => {
            if (searchQuery.length >= 2) searchInstruments(searchQuery);
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery, isSearchOpen, searchInstruments]);

    // Fetch Expiries
    useEffect(() => {
        if (selectedInstrument?.key) {
            fetchExpiryDates(selectedInstrument.key);
        }
    }, [selectedInstrument?.key, brokerStatus, fetchExpiryDates]);

    // Auto-select expiry
    useEffect(() => {
        if (expiryDates.length > 0 && !expiryDates.includes(expiryDate || "")) {
            setExpiryDate(expiryDates[0]);
        }
    }, [expiryDates, expiryDate, setExpiryDate]);

    // Fetch Option Chain Structure (ONCE when parameters change)
    useEffect(() => {
        if (brokerStatus === BrokerStatus.TOKEN_VALID && selectedInstrument?.key && expiryDate) {
            fetchOptionChain(selectedInstrument.key, expiryDate);
        }
    }, [brokerStatus, selectedInstrument?.key, expiryDate, fetchOptionChain]);

    const backendATM = optionChain?.atm_strike;

    // FIX #4: STABLE ATM (Critical for Performance - FIXES ISSUE #4)
    // ✅ Use backend's ATM snapshot (stable), NOT live spot price
    // Live spot updates should ONLY update prices (LTP), not structure (strikes)
    // Using live price causes unnecessary re-renders and potential memory issues
    const nearestStrike = useMemo(() => {
        return backendATM || roundToStep(optionChain?.spot_price || 0, optionChain?.strike_step || 50);
    }, [backendATM, optionChain?.spot_price, optionChain?.strike_step]);

    // Process Static Chain Data (Structure Only)
    // 🚨 PERFORMANCE CRITICAL: This memo MUST NOT depend on ltpMap or greeksMap!
    // It should only change when the option chain structure (strikes/keys) changes.
    // ✅ FIX #2 & #4: Properly sync REST API initial data with WebSocket live updates
    // ✅ FIX #5: Ensure chain initialization always has all required fields
    // ✅ FIX #6: Strict ATM Window Filtering (Phase 2)

    // Safety check: Ensure feedState exists before reading properties
    // ✅ FIX: Use FeedHealth as Source of Truth Override
    // If Backend sends FEED_HEALTH with state='LIVE', we trust it over stale feedState
    const serverSaysLive = feedHealth?.state === "LIVE";
    const isFeedLive = feedState?.status === "LIVE" || serverSaysLive;

    // logic: If server says LIVE, we are definitely NOT resetting, even if stale state says so.
    // logic: If server says LIVE, we are definitely NOT resetting, even if stale state says so.
    const isFeedResetting = (feedState?.status === "RESETTING") && !serverSaysLive;

    // 🔍 DEBUG: Inspect Feed Override Logic
    if (Math.random() < 0.01) {
        console.log("[useOptionChainData] 🩺 Feed Health Check:", {
            feedStateStatus: feedState?.status,
            feedHealthState: feedHealth?.state,
            serverSaysLive,
            isFeedResetting,
            hasLiveStrikes: feedState?.live_strikes?.length
        });
    }

    // Memoize complex objects to primitives for dependency array stability
    const hasLiveStrikes = liveStrikes.size > 0;

    const staticChain = useMemo(() => {
        if (!optionChain?.chain || !selectedInstrument) return [];

        const strikeStep = optionChain.strike_step || 50;
        // Use backend spot or 0 - DO NOT use live LTP here to avoid re-renders
        const spotPrice = optionChain.spot_price || 0;

        // 🟢 FILTERING LOGIC
        // If Market is OPEN and Feed is LIVE -> Filter by live_strikes
        // If Feed is RESETTING -> Return empty (Loading state)
        // If Market is CLOSED -> Return full chain
        let rowsToRender = optionChain.chain;

        // FIX: Use deterministic skeleton counter instead of Math.random()
        let skeletonCounter = 0;

        // Helper to create consistent OptionData structure (Avoids crash in UI)
        const createOptionData = (opt: any = {}, strike: number = 0, isSkeleton: boolean = false): OptionData => ({
            instrumentKey: opt.instrument_key || (isSkeleton ? `SKELETON_${strike}_${skeletonCounter++}` : ""),
            strike,
            ltp: opt.ltp ?? 0,
            volume: opt.volume ?? 0,
            oi: opt.oi ?? 0,
            close: opt.ltp ?? 0,
            iv: opt.iv ?? 0,
            delta: opt.delta ?? 0,
            theta: opt.theta ?? 0,
            gamma: opt.gamma ?? 0,
            vega: opt.vega ?? 0,
            bid: opt.bid ?? 0,
            ask: opt.ask ?? 0,
            bid_quantity: opt.bid_quantity ?? 0,
            ask_quantity: opt.ask_quantity ?? 0,
            symbol: opt.trading_symbol || "",
            instrumentName: opt.name || `${opt.trading_symbol || ''}`,
            lotSize: opt.lot_size || 0
        });

        if (marketStatus === "OPEN") {
            // 🔍 DEBUG: Why are we showing skeleton?
            if (process.env.NODE_ENV === 'development' && Math.random() < 0.05) {
                console.log("[useOptionChainData] 🟢 staticChain Calc:", {
                    isFeedResetting,
                    isFeedLive,
                    liveStrikesCount: liveStrikes.size,
                    feedStatus: feedState?.status
                });
            }

            if (isFeedResetting) {
                // ⚠️ RESET PHASE: Log but DO NOT BLOCK rendering of real data.
                // Keeping existing rows allows instantaneous binding when the new feed comes in.
                console.log("[useOptionChainData] ⚠️ Feed Resetting - Keeping previous/cached chain structure");
            }

            if (isFeedLive && hasLiveStrikes) {
                // ⚠️ STRICT FILTER DISABLED (Per User Request for Dimming)
                // We want to show ALL rows, but dim the ones not in liveStrikes.
                // Filter logic removed to allow OptionChainTable to handle visual state.

                // Debug log validation
                if (process.env.NODE_ENV === 'development' && Math.random() < 0.05) {
                    const mapped = optionChain.chain.map((r: any) => Number(r.strike_price));
                    const inSet = mapped.filter((s: number) => liveStrikes.has(s)).length;
                    console.log(`[useOptionChainData] Chain Validation: ${inSet}/${mapped.length} strikes match live set`);
                }
            }
        }

        return rowsToRender.map((row: any) => {
            const strike = row.strike_price;
            // Removed isATM calculation here - moved to OptionRow or derived external
            const isATM = false;

            const callOptions = row.call_options || {};
            const putOptions = row.put_options || {};

            return {
                strike,
                isATM,
                call: createOptionData(callOptions, strike),
                put: createOptionData(putOptions, strike),
            };
        }).sort((a: any, b: any) => a.strike - b.strike);
    }, [optionChain, selectedInstrument, hasLiveStrikes, isFeedResetting, marketStatus, feedState?.status, liveStrikes, feedHealth]);


    // ✅ FIX #3: Subscribe BEFORE rendering rows
    const isSubscribed = useMemo(() => {
        if (!optionChain || !selectedInstrument?.key) return false;
        // FIX: Allow 'connecting' state - socket is physically open and can receive subscription messages
        // Changed from: if (feedStatus !== 'connected')
        // To: Only block on truly bad states
        if (feedStatus === 'disconnected' || feedStatus === 'unavailable' || feedStatus === 'market_closed') return false;

        // Check if current active instruments in store match what's needed for this chain
        // We only care if the underlying is correct for now (simple check)
        // or just if switchUnderlying has been called for this set.
        // For simplicity: if feed is connected and we have an option chain, 
        // the useEffect below will trigger switchUnderlying.
        // We only want to 'render' when that's done.

        // Let's use a more robust check: are there enough active instruments?
        return activeInstruments.length > 0;
    }, [optionChain, selectedInstrument?.key, feedStatus, activeInstruments.length]);

    const isTradeDisabled = brokerStatus !== BrokerStatus.TOKEN_VALID || engineStatus === "PAUSED";
    const strikeStep = optionChain?.strike_step; // Restored definition here

    // 🔍 DEBUG: Log spot price computation
    useEffect(() => {
        const ltpMapValue = selectedInstrument ? ltpMap[selectedInstrument.key] : undefined;
        const indexKeys = Object.keys(ltpMap).filter(k => k.includes("INDEX") || k.includes("Nifty"));
        console.log("[useOptionChainData] Spot Price Calculation:", {
            selectedInstrument: selectedInstrument?.key,
            exactKeyUsed: selectedInstrument?.key,
            keysInLtpMap_INDEX: indexKeys,
            marketStatus,
            "ltpMap[key] (WS)": ltpMapValue,
            "optionChain?.spot_price (REST)": optionChain?.spot_price,
            "computed currentSpotPrice": currentSpotPrice,
            "Deviation %": optionChain?.spot_price ?
                (Math.abs((ltpMapValue || 0) - optionChain.spot_price) / optionChain.spot_price * 100).toFixed(1) + "%" : "N/A"
        });

        // 🔍 DEBUG: Inspect First Row Keys
        if (staticChain.length > 0) {
            const first = staticChain[0];
            const firstCallKey = first.call?.instrumentKey;
            const firstPutKey = first.put?.instrumentKey;
            const callLtp = ltpMap[firstCallKey] || "MISSING";

            console.log("[useOptionChainData] 🔑 First Row Keys:", {
                strike: first.strike,
                callKey: firstCallKey,
                putKey: firstPutKey,
                "callKey in ltpMap?": !!ltpMap[firstCallKey],
                "Value in store": callLtp
            });
        }

    }, [currentSpotPrice, optionChain?.spot_price, ltpMap, selectedInstrument, marketStatus]);

    return {
        // State
        selectedInstrument: selectedInstrument || { name: "NIFTY 50", key: "NSE_INDEX|Nifty 50" },
        setSelectedInstrument,
        searchQuery,
        setSearchQuery,
        expiryDate: expiryDate || "",
        setExpiryDate,
        isSearchOpen,
        setIsSearchOpen,

        // Store data
        staticChain,
        ltpMap,
        previousLtpMap,
        isLoadingChain,
        searchResults,
        expiryDates,
        brokerStatus,
        engineStatus,
        marketStatus,
        strikeStep,
        currentSpotPrice,
        nearestStrike,
        isTradeDisabled,
        isReady: isSubscribed && !isLoadingChain,

        // Actions
        fetchOptionChain,
        searchInstruments,
        // ✅ EXPOSE NEW PROPS
        liveStrikes,
        currentATMStrike: nearestStrike
    };
};

function roundToStep(value: number, step: number) {
    if (!step) return value;
    return Math.round(value / step) * step;
}
