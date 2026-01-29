import React, { useMemo, useState, useCallback, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { OptionChainRow, OptionData } from "@/types/trading";
import { useMarketStore } from "@/stores/marketStore";


interface OptionRowProps {
    row: OptionChainRow;
    callKey: string;
    putKey: string;
    columns: any;
    isTradeDisabled: boolean;
    useCompactButtons: boolean;
    handleBuySell: (option: OptionData, type: "CE" | "PE", action: "BUY" | "SELL") => void;
    getLtpFlashClass?: null;
    isATM?: boolean; // ✅ Derived Prop
    isLive?: boolean; // ✅ Derived Prop (for Dimming)
}

export const OptionRow: React.FC<OptionRowProps> = React.memo(({
    row,
    callKey,
    putKey,
    columns,
    isTradeDisabled,
    useCompactButtons,
    handleBuySell,
    isATM = false,
    isLive = true, // Default to true to prevent accidental dimming if prop missing
}) => {
    // ✅ FIX #1: Call ALL hooks at the top level BEFORE any conditional logic
    // Get market data using Zustand selectors directly (not nested in useMemo)
    const callTick = useMarketStore((s) => callKey ? s.marketData[callKey] : undefined);
    const putTick = useMarketStore((s) => putKey ? s.marketData[putKey] : undefined);
    const feedStatus = useMarketStore((s) => s.feedStatus);

    // ✅ FIX #2: Persist Last Known LTP - moved BEFORE conditional returns
    const [lastCallLtp, setLastCallLtp] = useState(row.call.ltp);
    const [lastPutLtp, setLastPutLtp] = useState(row.put.ltp);

    const isMarketClosed = feedStatus === 'market_closed' || feedStatus === 'disconnected';

    // ✅ NOW we can do early returns (after all hooks are called)
    if (!callKey || !putKey) {
        console.warn("[OptionRow] Missing instrumentKey for strike", row.strike);
        return null;
    }

    // ✅ FIX #3: useEffect hooks called at top level (after conditional, but after all hook calls)
    useEffect(() => {
        if (callTick?.ltp && callTick.ltp > 0) setLastCallLtp(callTick.ltp);
    }, [callTick?.ltp]);

    useEffect(() => {
        if (putTick?.ltp && putTick.ltp > 0) setLastPutLtp(putTick.ltp);
    }, [putTick?.ltp]);

    // 🔴 Enhanced debug logging with throttling
    if (callKey && !callTick && !row.isSkeleton && Math.random() < 0.01) {
        console.warn(`[OptionRow] ❌ Strike ${row.strike} CALL: No tick data. Key: ${callKey}`);
        console.warn(`[OptionRow]    Static fallback: LTP=${row.call.ltp}, Vol=${row.call.volume}, OI=${row.call.oi}`);
    }
    if (putKey && !putTick && !row.isSkeleton && Math.random() < 0.01) {
        console.warn(`[OptionRow] ❌ Strike ${row.strike} PUT: No tick data. Key: ${putKey}`);
        console.warn(`[OptionRow]    Static fallback: LTP=${row.put.ltp}, Vol=${row.put.volume}, OI=${row.put.oi}`);
    }

    // ✅ FIX #4: Extract live values - use a memoized helper function (no hooks inside)
    const getLiveValue = useCallback((tick: any, field: string, staticFallback: any) => {
        if (!tick) return staticFallback;
        const fieldToAccess = field === 'vol' ? 'volume' : field;
        let val = tick[fieldToAccess];

        if (typeof val === 'string' && !isNaN(Number(val))) {
            val = Number(val);
        }

        if (val !== undefined && val !== null && val !== 0) {
            return val;
        }
        return staticFallback ?? 0;
    }, []);

    // ✅ SOLUTION: Hybrid Logic with better fallback chain
    const getHybridLtp = useCallback((tick: any, staticLtp: number, persistedLtp: number) => {
        // 1. If WebSocket tick exists and has valid LTP, use it (highest priority)
        if (tick && tick.ltp && tick.ltp > 0) {
            return tick.ltp;
        }

        // 2. If we have a persisted (last known) good LTP, use it (fallback for stale feeds)
        if (persistedLtp && persistedLtp > 0) {
            return persistedLtp;
        }

        // 3. If static REST API data exists, use it (initial load or market closed)
        if (staticLtp && staticLtp > 0) {
            return staticLtp;
        }

        // 4. All sources exhausted - return 0 (UI will render as "-")
        if (Math.random() < 0.05) {
            console.warn(`[OptionRow] No valid LTP found: tick=${tick?.ltp}, persisted=${persistedLtp}, static=${staticLtp}`);
        }
        return 0;
    }, []);

    const callLtp = getHybridLtp(callTick, row.call.ltp, lastCallLtp);
    const putLtp = getHybridLtp(putTick, row.put.ltp, lastPutLtp);

    const callPrevClose = row.call.close || row.call.ltp;
    const putPrevClose = row.put.close || row.put.ltp;

    const calculateChange = useCallback((ltp: number, prev: number) => {
        if (!prev || prev === 0) return { change: 0, percent: 0 };
        const change = ltp - prev;
        const percent = (change / prev) * 100;
        return { change, percent };
    }, []);

    const callChange = calculateChange(callLtp as number, callPrevClose);
    const putChange = calculateChange(putLtp as number, putPrevClose);

    // Call Actions Data Construction
    const callActionData = useMemo(() => ({
        instrumentKey: callKey,
        instrumentName: row.call.instrumentName || `CALL ${row.strike}`,
        strike: row.strike,
        optionType: "CE",
        ltp: callLtp,
        symbol: row.call.symbol
    }), [callKey, row.call.instrumentName, row.call.symbol, row.strike, callLtp]);

    const putActionData = useMemo(() => ({
        instrumentKey: putKey,
        instrumentName: row.put.instrumentName || `PUT ${row.strike}`,
        strike: row.strike,
        optionType: "PE",
        ltp: putLtp,
        symbol: row.put.symbol
    }), [putKey, row.put.instrumentName, row.put.symbol, row.strike, putLtp]);

    // ✅ FIX #5: Memoize getLiveValue results
    const callOI = useMemo(() => getLiveValue(callTick, 'oi', row.call.oi), [callTick, row.call.oi, getLiveValue]);
    const callVolume = useMemo(() => getLiveValue(callTick, 'volume', row.call.volume), [callTick, row.call.volume, getLiveValue]);
    const callDelta = useMemo(() => getLiveValue(callTick, 'delta', row.call.delta), [callTick, row.call.delta, getLiveValue]);
    const callTheta = useMemo(() => getLiveValue(callTick, 'theta', row.call.theta), [callTick, row.call.theta, getLiveValue]);
    const callGamma = useMemo(() => getLiveValue(callTick, 'gamma', row.call.gamma), [callTick, row.call.gamma, getLiveValue]);
    const callVega = useMemo(() => getLiveValue(callTick, 'vega', row.call.vega), [callTick, row.call.vega, getLiveValue]);
    const callIV = useMemo(() => getLiveValue(callTick, 'iv', row.call.iv), [callTick, row.call.iv, getLiveValue]);

    const putOI = useMemo(() => getLiveValue(putTick, 'oi', row.put.oi), [putTick, row.put.oi, getLiveValue]);
    const putVolume = useMemo(() => getLiveValue(putTick, 'volume', row.put.volume), [putTick, row.put.volume, getLiveValue]);
    const putDelta = useMemo(() => getLiveValue(putTick, 'delta', row.put.delta), [putTick, row.put.delta, getLiveValue]);
    const putTheta = useMemo(() => getLiveValue(putTick, 'theta', row.put.theta), [putTick, row.put.theta, getLiveValue]);
    const putGamma = useMemo(() => getLiveValue(putTick, 'gamma', row.put.gamma), [putTick, row.put.gamma, getLiveValue]);
    const putVega = useMemo(() => getLiveValue(putTick, 'vega', row.put.vega), [putTick, row.put.vega, getLiveValue]);
    const putIV = useMemo(() => getLiveValue(putTick, 'iv', row.put.iv), [putTick, row.put.iv, getLiveValue]);

    const renderChange = useCallback((data: { change: number; percent: number }) => {
        if (data.change === 0) return "-";
        const color = data.change > 0 ? "text-profit" : "text-loss";
        return (
            <span className={cn("text-[10px]", color)}>
                {data.percent > 0 ? "+" : ""}{data.percent.toFixed(2)}%
            </span>
        );
    }, []);

    // ✅ Bid/Ask Tooltip Helper
    const getTooltip = useCallback((tick: any) => {
        if (!tick) return undefined;

        const parsePrice = (val: any) => {
            if (val === undefined || val === null) return 0;
            const num = Number(val);
            return isNaN(num) ? 0 : num;
        };

        const bid = parsePrice(tick.bid);
        const ask = parsePrice(tick.ask);
        const bidSim = tick.bid_simulated === 'True' || tick.bid_simulated === true;
        const askSim = tick.ask_simulated === 'True' || tick.ask_simulated === true;

        if (bid === 0 && ask === 0) return undefined;

        const spread = parsePrice(tick.spread);
        return `Bid: ₹${bid.toFixed(2)} (${bidSim ? 'SIM' : 'REAL'}) | Ask: ₹${ask.toFixed(2)} (${askSim ? 'SIM' : 'REAL'}) | Spread: ₹${spread.toFixed(2)}`;
    }, []);

    // Helper for Status Badge
    const renderStatusBadge = useCallback((isSimulated: boolean) => {
        if (isSimulated) return <span className="text-[8px] text-yellow-500 bg-yellow-500/10 px-1 rounded ml-1">SIM</span>;
        return <span className="text-[8px] text-green-500 bg-green-500/10 px-1 rounded ml-1">REAL</span>;
    }, []);

    // Helper to get SIM flag from tick safely (handling string/bool form from Redis)
    const isSimulated = useCallback((val: any) => val === 'True' || val === true, []);

    return (
        <tr className={cn(
            "border-b border-border/50 transition-colors hover:bg-muted/30 group",
            !isLive && "opacity-40 grayscale-[0.8]" // ✅ Dim non-live strikes
        )}>
            {/* CALLS */}
            {columns.oi && <td className="call-column px-2 py-1 text-right font-mono text-xs text-muted-foreground group-hover:text-foreground">{callOI > 0 ? (callOI / 1000).toFixed(0) + 'K' : '-'}</td>}
            {columns.volume && <td className="call-column px-2 py-1 text-right font-mono text-xs text-muted-foreground group-hover:text-foreground">{callVolume > 0 ? (callVolume / 1000).toFixed(0) + 'K' : '-'}</td>}
            {columns.delta && <td className="call-column px-2 py-1 text-right font-mono text-xs text-muted-foreground">{typeof callDelta === 'number' ? callDelta.toFixed(2) : '-'}</td>}
            {columns.theta && <td className="call-column px-2 py-1 text-right font-mono text-xs text-muted-foreground">{typeof callTheta === 'number' ? callTheta.toFixed(1) : '-'}</td>}
            {columns.gamma && <td className="call-column px-2 py-1 text-right font-mono text-xs text-muted-foreground">{typeof callGamma === 'number' ? callGamma.toFixed(4) : '-'}</td>}
            {columns.vega && <td className="call-column px-2 py-1 text-right font-mono text-xs text-muted-foreground">{typeof callVega === 'number' ? callVega.toFixed(1) : '-'}</td>}
            {columns.iv && <td className="call-column px-2 py-1 text-right font-mono text-xs text-muted-foreground">{typeof callIV === 'number' ? callIV.toFixed(1) : '-'}%</td>}

            {columns.change && <td className="call-column px-2 py-1 text-right font-mono text-xs text-muted-foreground">{renderChange(callChange)}</td>}

            <td
                className={cn("call-column px-2 py-1 text-right font-mono text-sm font-semibold text-foreground cursor-help")}
                title={getTooltip(callTick)}
            >
                {/* ✅ PHASE 2: HEARTBEAT ANIMATION (Resets on update) */}
                <span key={callTick?.lastUpdated || 'static'} className="animate-fade-stale block">
                    {typeof callLtp === 'number' ? callLtp.toFixed(2) : callLtp}
                    {/* Status Badge */}
                    {callTick && renderStatusBadge(isSimulated(callTick.ask_simulated))}
                    {/* Note: Ask Simulated applies to BUYING the Call. Bid Sim applies to SELLING. 
                        Usually we show generalized status? 
                        Let's use 'ask_simulated' for the Ask Price (which is usually the LTP proxy or close to it)
                        Actually, LTP comes from Last Trade. 
                        But we want to show if LIQUIDITY is real.
                        If Bid/Ask is simulated, we show SIM.
                    */}
                </span>
            </td>

            <td className="call-column relative px-0 py-0 text-center w-[60px]">
                <div className="absolute inset-0 flex items-center justify-center gap-0 opacity-100">
                    <Button
                        size="sm"
                        variant="ghost"
                        disabled={isTradeDisabled}
                        onClick={() => handleBuySell(callActionData as any, "CE", "BUY")}
                        className={cn(
                            "font-bold text-profit hover:bg-profit/10",
                            useCompactButtons ? "h-5 px-1 text-[9px]" : "h-6 px-2 text-[11px]"
                        )}
                    >
                        B
                    </Button>
                    <Button
                        size="sm"
                        variant="ghost"
                        disabled={isTradeDisabled}
                        onClick={() => handleBuySell(callActionData as any, "CE", "SELL")}
                        className={cn(
                            "font-bold text-loss hover:bg-loss/10",
                            useCompactButtons ? "h-5 px-1 text-[9px]" : "h-6 px-2 text-[11px]"
                        )}
                    >
                        S
                    </Button>
                </div>
            </td>

            {/* STRIKE */}
            <td className={cn("px-3 py-1 text-center min-w-[100px] border-x border-border/50", isATM ? "bg-atm/10 relative" : "bg-secondary")}>
                <div className="flex items-center justify-center gap-1">
                    <span className={cn("font-mono text-sm font-bold", isATM ? "text-atm" : "text-foreground")}>{row.strike}</span>
                    {isATM && <span className="absolute right-1 top-1 text-[7px] bg-atm text-primary-foreground px-0.5 rounded-sm">ATM</span>}
                </div>
            </td>

            {/* PUTS */}
            <td className="put-column relative px-0 py-0 text-center w-[60px]">
                <div className="absolute inset-0 flex items-center justify-center gap-0 opacity-100">
                    <Button
                        size="sm"
                        variant="ghost"
                        disabled={isTradeDisabled}
                        onClick={() => handleBuySell(putActionData as any, "PE", "BUY")}
                        className={cn(
                            "font-bold text-profit hover:bg-profit/10",
                            useCompactButtons ? "h-5 px-1 text-[9px]" : "h-6 px-2 text-[11px]"
                        )}
                    >
                        B
                    </Button>
                    <Button
                        size="sm"
                        variant="ghost"
                        disabled={isTradeDisabled}
                        onClick={() => handleBuySell(putActionData as any, "PE", "SELL")}
                        className={cn(
                            "font-bold text-loss hover:bg-loss/10",
                            useCompactButtons ? "h-5 px-1 text-[9px]" : "h-6 px-2 text-[11px]"
                        )}
                    >
                        S
                    </Button>
                </div>
            </td>

            <td
                className={cn("put-column px-2 py-1 text-right font-mono text-sm font-semibold text-foreground cursor-help")}
                title={getTooltip(putTick)}
            >
                {/* ✅ PHASE 2: HEARTBEAT ANIMATION */}
                <span key={putTick?.lastUpdated || 'static'} className="animate-fade-stale block">
                    {typeof putLtp === 'number' ? putLtp.toFixed(2) : putLtp}
                    {putTick && renderStatusBadge(isSimulated(putTick.bid_simulated))}
                </span>
            </td>
            {columns.change && <td className="put-column px-2 py-1 text-right font-mono text-xs text-muted-foreground">{renderChange(putChange)}</td>}

            {columns.iv && <td className="put-column px-2 py-1 text-left font-mono text-xs text-muted-foreground">{typeof putIV === 'number' ? putIV.toFixed(1) : '-'}%</td>}
            {columns.vega && <td className="put-column px-2 py-1 text-left font-mono text-xs text-muted-foreground">{typeof putVega === 'number' ? putVega.toFixed(1) : '-'}</td>}
            {columns.gamma && <td className="put-column px-2 py-1 text-left font-mono text-xs text-muted-foreground">{typeof putGamma === 'number' ? putGamma.toFixed(4) : '-'}</td>}
            {columns.theta && <td className="put-column px-2 py-1 text-left font-mono text-xs text-muted-foreground">{typeof putTheta === 'number' ? putTheta.toFixed(1) : '-'}</td>}
            {columns.delta && <td className="put-column px-2 py-1 text-left font-mono text-xs text-muted-foreground">{typeof putDelta === 'number' ? putDelta.toFixed(2) : '-'}</td>}
            {columns.volume && <td className="put-column px-2 py-1 text-right font-mono text-xs text-muted-foreground group-hover:text-foreground">{putVolume > 0 ? (putVolume / 1000).toFixed(0) + 'K' : '-'}</td>}
            {columns.oi && <td className="put-column px-2 py-1 text-right font-mono text-xs text-muted-foreground group-hover:text-foreground">{putOI > 0 ? (putOI / 1000).toFixed(0) + 'K' : '-'}</td>}
        </tr>
    );
});

OptionRow.displayName = "OptionRow";
