import React, { useState, useCallback } from "react";
import { logger } from "@/lib/logger";
import { motion } from "framer-motion";
import { useUIStore } from "@/stores/uiStore";
import { OptionData } from "@/types/trading";
import { useOptionChainData } from "@/hooks/useOptionChainData";
import { useMarketStore } from "@/stores/marketStore"; // ✅ Phase 2
import { OptionChainHeader } from "./OptionChainHeader";
import { OptionChainTable } from "./OptionChainTable";

export const OptionChain: React.FC = () => {
  // UI State - Column Visibility
  const [columns, setColumns] = useState({
    oi: true,
    delta: false,
    theta: false,
    iv: true,
    gamma: false,
    vega: false,
    volume: false,
    change: true,
  });

  const toggleColumn = useCallback((key: keyof typeof columns) => {
    setColumns(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Data Logic Hook
  const {
    selectedInstrument,
    setSelectedInstrument,
    searchQuery,
    setSearchQuery,
    expiryDate,
    setExpiryDate,
    isSearchOpen,
    setIsSearchOpen,
    staticChain,
    ltpMap,
    previousLtpMap,
    isLoadingChain,
    searchResults,
    expiryDates,
    brokerStatus,
    marketStatus,
    strikeStep,
    currentSpotPrice,
    isTradeDisabled,
    isReady,
    liveStrikes, // ✅ O(1) Set
    currentATMStrike, // ✅ Derived ATM
  } = useOptionChainData();

  const { feedState, feedStatus } = useMarketStore(); // ✅ Phase 2

  // Filtering is now handled in the hook, just use staticChain
  const visibleChain = staticChain;

  // 🔴 DEBUG: Inspect Feed State and Chain
  React.useEffect(() => {
    logger.debug("OptionChain", "🔍 Debug State", {
      feedStatus,
      "feedState.status": feedState?.status,
      "feedState.live_strikes": feedState?.live_strikes?.length,
      "visibleChain.length": visibleChain.length,
      "Sample Row (0)": visibleChain[0] ? {
        strike: visibleChain[0].strike,
        callKey: visibleChain[0].call?.instrumentKey,
        isSkeleton: visibleChain[0].call?.instrumentKey?.startsWith("SKELETON")
      } : "None"
    });

    // ✅ Fix 3: Add render guard logging (User Request)
    console.log("OptionChain render guard", {
      hasSpot: !!currentSpotPrice,
      strikeCount: visibleChain.length,
      wsKeys: Object.keys(ltpMap).length,
      marketStatus,
      isTradeDisabled,
      feedStatus
    });

  }, [feedState, visibleChain, feedStatus]);

  const { openOrderModal } = useUIStore();

  // 🔴 MARKET CLOSED CHECK: Disable trading when market is closed
  const isMarketClosed = marketStatus === "CLOSED";

  const handleBuySell = useCallback((option: OptionData, optionType: "CE" | "PE", action: "BUY" | "SELL") => {
    if (!option.instrumentKey) return;
    openOrderModal({
      instrumentKey: option.instrumentKey,
      instrumentName: `${selectedInstrument.name} ${option.strike} ${optionType}`,
      strike: option.strike,
      optionType,
      ltp: option.ltp,
    });
  }, [openOrderModal, selectedInstrument.name, isMarketClosed]);



  const getColSpan = useCallback(() => {
    let count = 2; // LTP, Action (fixed)
    if (columns.change) count++;
    if (columns.oi) count++;
    if (columns.volume) count++;
    if (columns.iv) count++;
    if (columns.delta) count++;
    if (columns.theta) count++;
    if (columns.gamma) count++;
    if (columns.vega) count++;
    return count;
  }, [columns]);

  const visibleColumnCount = getColSpan();
  const useCompactButtons = visibleColumnCount > 6;

  return (
    <div className="trade-card overflow-hidden h-full flex flex-col">
      <OptionChainHeader
        selectedInstrument={selectedInstrument}
        setSelectedInstrument={setSelectedInstrument}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        searchResults={searchResults}
        isSearchOpen={isSearchOpen}
        setIsSearchOpen={setIsSearchOpen}
        expiryDates={expiryDates}
        expiryDate={expiryDate}
        setExpiryDate={setExpiryDate}
        strikeStep={strikeStep}
        backendATM={currentATMStrike}
        columns={columns}
        toggleColumn={toggleColumn}
        isTradeDisabled={isTradeDisabled}
        brokerStatus={brokerStatus}
        marketStatus={marketStatus}
      />

      {/* Spot Price Ticker - Always Visible */}
      <div className="relative border-b border-border bg-secondary/30 px-2 md:px-4 py-2 md:py-3 flex-shrink-0">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 md:gap-3">
            <span className="text-xs md:text-sm text-muted-foreground">Spot:</span>
            <motion.span
              key={currentSpotPrice}
              initial={{ scale: 1.1, color: "hsl(var(--success))" }}
              animate={{ scale: 1, color: "hsl(var(--foreground))" }}
              className="font-mono text-base md:text-lg font-bold"
            >
              {currentSpotPrice.toFixed(2)}
            </motion.span>

            {/* Live/Closed Indicator */}
            {isMarketClosed ? (
              <span className="text-xs px-2 py-0.5 bg-red-500/20 text-red-600 rounded border border-red-500/50 font-semibold">
                🔴 CLOSED
              </span>
            ) : (
              <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-600 rounded border border-green-500/50 animate-pulse font-semibold">
                🟢 LIVE
              </span>
            )}
          </div>
          <div className="flex items-center gap-1 md:gap-2 text-xs md:text-sm">
            <span className="text-muted-foreground hidden sm:inline">Spot Strike:</span>
            <span className="font-mono font-semibold text-atm">{currentATMStrike}</span>
          </div>
        </div>
      </div>

      {/* Option Chain Table - Always Visible */}
      <OptionChainTable
        data={visibleChain} // ✅ Phase 2: Use Filtered Data
        isLoading={isLoadingChain || !isReady}
        columns={columns}
        currentSpotPrice={currentSpotPrice}
        isTradeDisabled={isTradeDisabled}
        handleBuySell={handleBuySell}
        getColSpan={getColSpan}
        currentATMStrike={currentATMStrike}
        liveStrikes={liveStrikes}
      />
    </div>
  );
};
