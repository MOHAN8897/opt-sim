import React from "react";
import { motion } from "framer-motion";
import { X, TrendingUp, TrendingDown } from "lucide-react";
import { useTradeStore, Trade } from "@/stores/tradeStore";
import { useMarketStore } from "@/stores/marketStore";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface TradeCardProps {
  trade: Trade;
}

const TradeCard: React.FC<TradeCardProps> = ({ trade }) => {
  const { ltpMap } = useMarketStore();
  const { closeTrade } = useTradeStore();

  // Logic: 
  // Trade row represents a position.
  // Invested Amount = Entry Price * Quantity
  // Current Value = LTP * Quantity
  // P&L = Current Value - Invested Amount (for Long)
  //     = Invested Amount - Current Value (for Short)

  const ltpVal = ltpMap[trade.instrumentKey];
  const currentLtp = (ltpVal && Number(ltpVal) > 0) ? Number(ltpVal) : trade.entryPrice;
  const investedAmount = trade.entryPrice * trade.quantity;
  const currentValue = currentLtp * trade.quantity;

  // Calculate P&L based on Side
  let unrealizedPnl = 0;
  if (trade.side === "BUY") {
    unrealizedPnl = currentValue - investedAmount;
  } else {
    unrealizedPnl = investedAmount - currentValue; // Short: Profit if Value goes down
  }

  // FIX: Guard against division by zero and non-finite values
  const pnlPercent = investedAmount !== 0 && Number.isFinite(investedAmount) 
    ? (unrealizedPnl / investedAmount) * 100 
    : 0;
  const isProfitable = unrealizedPnl >= 0;

  const handleExit = () => {
    closeTrade(trade.id, currentLtp);
    toast.success("Trade Closed", {
      description: `P&L: ${unrealizedPnl >= 0 ? "+" : ""}₹${unrealizedPnl.toFixed(2)}`,
    });
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className={cn(
        "trade-card relative overflow-hidden p-4",
        "before:absolute before:left-0 before:top-0 before:h-full before:w-1",
        isProfitable
          ? "before:bg-profit before:shadow-[0_0_15px_hsl(var(--profit)/0.5)]"
          : "before:bg-loss before:shadow-[0_0_15px_hsl(var(--loss)/0.5)]"
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          {/* Header */}
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-xs font-bold",
                trade.side === "BUY" ? "bg-profit/20 text-profit" : "bg-loss/20 text-loss"
              )}
            >
              {trade.side}
            </span>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-xs font-medium",
                trade.optionType === "CE" ? "bg-call/20 text-call" : "bg-put/20 text-put"
              )}
            >
              {trade.optionType}
            </span>
          </div>

          {/* Instrument Name */}
          <h3 className="mt-2 font-semibold text-foreground">
            {trade.tradingSymbol || `${trade.instrumentName} ${trade.strike} ${trade.optionType}`}
          </h3>

          {/* Details */}
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div>
              <p className="text-muted-foreground">Invested</p>
              <p className="font-mono font-medium text-foreground">₹{investedAmount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</p>
            </div>
            <div>
              <p className="text-muted-foreground">LTP</p>
              <p className="font-mono font-medium text-foreground live-pulse">₹{currentLtp.toFixed(2)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Qty</p>
              <p className="font-mono font-medium text-foreground">{trade.quantity}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Avg. Price</p>
              <p className="font-mono font-medium text-foreground">₹{trade.entryPrice.toFixed(2)}</p>
            </div>

            {/* ✅ V4.0 Slippage Feedback */}
            {trade.slippage !== undefined && trade.slippage !== 0 && (
              <div className="col-span-2 mt-1 border-t border-border/50 pt-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Slippage:</span>
                  <span className={cn("font-mono font-bold", trade.slippage > 0 ? "text-loss" : "text-profit")}>
                    {trade.slippage > 0 ? "+" : ""}{trade.slippage.toFixed(2)}
                    <span className="text-[9px] font-normal ml-1 text-muted-foreground">
                      (Exp: {trade.expectedPrice?.toFixed(2)})
                    </span>
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* PnL Section */}
        <div className="flex flex-col items-end gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={handleExit}
            className="h-8 w-8 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
          >
            <X className="h-4 w-4" />
          </Button>

          <div className="text-right">
            <p className="text-xs text-muted-foreground">Unrealized P&L</p>
            <div className="flex items-center gap-1">
              {isProfitable ? (
                <TrendingUp className="h-4 w-4 text-profit" />
              ) : (
                <TrendingDown className="h-4 w-4 text-loss" />
              )}
              <p className={cn("text-xl font-bold tabular-nums", isProfitable ? "pnl-profit" : "pnl-loss")}>
                {unrealizedPnl >= 0 ? "+" : ""}₹{Math.abs(unrealizedPnl).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
            </div>
            <p className={cn("text-xs tabular-nums", isProfitable ? "text-profit" : "text-loss")}>
              ({pnlPercent > 0 ? "+" : pnlPercent < 0 ? "-" : ""}{Math.abs(pnlPercent).toFixed(2)}%)
            </p>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export const TradeManager: React.FC = () => {
  const { openTrades, fetchTrades } = useTradeStore();

  React.useEffect(() => {
    fetchTrades();
  }, []);

  return (
    <div className="trade-card overflow-hidden">
      <div className="border-b border-border p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Open Positions</h2>
          <span className="rounded-full bg-primary/20 px-3 py-1 text-sm font-medium text-primary">
            {openTrades.length} Active
          </span>
        </div>
      </div>

      <div className="p-4">
        {openTrades.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              <TrendingUp className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-medium text-foreground">No Open Positions</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Start trading from the option chain
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {openTrades.map((trade) => (
              <TradeCard key={trade.id} trade={trade} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
