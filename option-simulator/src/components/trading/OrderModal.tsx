import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Check, Loader2, AlertCircle, TrendingUp, TrendingDown } from "lucide-react";
import { useUIStore } from "@/stores/uiStore";
import { useTradeStore, Trade } from "@/stores/tradeStore";
import { useMarketStore } from "@/stores/marketStore";
import { useAuthStore } from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export const OrderModal: React.FC = () => {
  const { orderModalOpen, selectedOption, closeOrderModal } = useUIStore();
  const { placeTrade, openTrades, closeTrade } = useTradeStore();
  const { user } = useAuthStore();

  // 🔴 FIX #1: Guard against null selectedOption to prevent blank page
  // This prevents the modal from rendering when selectedOption becomes null due to stale closures
  if (!selectedOption) {
    return null; // Don't render if no option is selected
  }

  const instrumentKey = selectedOption?.instrumentKey;
  const tick = useMarketStore(s => instrumentKey ? s.marketData[instrumentKey] : undefined);

  // ✅ FIX: Prioritize Live Tick -> Fallback to Static/Snapshot LTP (for Market Closed)
  // Backend sends strings for precision, so strictly parse to Number
  const liveTickLtp = tick?.ltp ? Number(tick.ltp) : 0;
  const liveBid = tick?.bid ? Number(tick.bid) : 0;
  const liveAsk = tick?.ask ? Number(tick.ask) : 0;

  const staticLtp = selectedOption?.ltp ? Number(selectedOption.ltp) : 0;

  const liveLtp = (!isNaN(liveTickLtp) && liveTickLtp > 0)
    ? liveTickLtp
    : (staticLtp || 0);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [lots, setLots] = useState(1);
  const [orderType, setOrderType] = useState<"MARKET" | "LIMIT">("MARKET");
  const [limitPrice, setLimitPrice] = useState<string>("");

  // ✅ DYNAMIC LOT SIZE
  const lotSize = selectedOption?.lotSize || 50;

  // ✅ FIX: Robust Key Matching (Normalize separators)
  const normalizeKey = (key: string) => key?.replace(/[:|]/g, "_") || "";

  // Find existing position for this instrument
  const existingPosition = openTrades.find(
    (trade) => normalizeKey(trade.instrumentKey) === normalizeKey(selectedOption?.instrumentKey || "")
  );

  // Reset form when modal opens
  useEffect(() => {
    if (orderModalOpen && selectedOption) {
      setSide("BUY");
      setLots(1);
      setOrderType("MARKET");
      setLimitPrice(liveLtp > 0 ? liveLtp.toFixed(2) : "");
    }
  }, [orderModalOpen, selectedOption, liveLtp]);

  // ✅ V4.0 PRICE LOGIC: Buy @ Ask, Sell @ Bid
  const getMarketPrice = () => {
    if (side === "BUY") return (liveAsk > 0 ? liveAsk : liveLtp);
    return (liveBid > 0 ? liveBid : liveLtp);
  };

  const quantity = lots * lotSize; // ✅ USE DYNAMIC LOT SIZE
  const executionPrice = orderType === "MARKET" ? getMarketPrice() : parseFloat(limitPrice) || 0;
  const orderValue = quantity * executionPrice;

  // Calculate margin required (simplified - 20% of order value for sell, full for buy)
  const marginRequired = side === "SELL" ? orderValue * 0.2 : orderValue;
  const availableBalance = user?.virtual_balance || 0; // ✅ BALANCE

  // Validate sell order
  const canSell = existingPosition && existingPosition.side === "BUY" && existingPosition.quantity >= quantity;

  // Validate buy order (Balance check)
  const canBuy = availableBalance >= marginRequired;

  const handleSubmit = async () => {
    if (!selectedOption) return;

    // ✅ LOW FIX: Input validation
    if (lots <= 0 || lots > 1000) {
      toast.error("Invalid Quantity", {
        description: "Lots must be between 1 and 1000"
      });
      return;
    }

    // Validate LTP
    if (liveLtp === 0) {
      toast.error("No market data available", {
        description: "Please wait for live price updates or try again later"
      });
      return;
    }

    // Validate SELL order
    if (side === "SELL" && !canSell) {
      toast.error("Cannot Sell", {
        description: existingPosition
          ? `You only have ${existingPosition.quantity} shares to sell`
          : "You don't own any shares of this instrument"
      });
      return;
    }

    // ✅ VALIDATE BUY BALANCE
    if (side === "BUY" && !canBuy) {
      toast.error("Insufficient Balance", {
        description: `Required: ₹${marginRequired.toLocaleString("en-IN")}, Available: ₹${availableBalance.toLocaleString("en-IN")}`
      });
      return;
    }

    setIsSubmitting(true);

    try {
      // If selling an existing position
      if (side === "SELL" && existingPosition && existingPosition.side === "BUY") {
        await closeTrade(existingPosition.id, liveLtp);
        setIsSubmitting(false);
        setShowSuccess(true);
        setTimeout(() => {
          setShowSuccess(false);
          closeOrderModal();
          toast.success("Position Closed! 🎯", {
            description: `Sold ${existingPosition.quantity} x ${selectedOption.instrumentName} @ ₹${liveLtp.toFixed(2)}`,
          });
        }, 1200);
        return;
      }

      // Place new trade
      const tradeDetails = {
        instrumentKey: selectedOption.instrumentKey,
        instrumentName: selectedOption.instrumentName,
        symbol: (selectedOption as any).symbol || selectedOption.instrumentName.split(" ")[0] || "NIFTY",
        strike: selectedOption.strike,
        optionType: selectedOption.optionType,
        side: side,
        quantity: quantity,
        entryPrice: executionPrice,
      };

      await placeTrade(tradeDetails);

      setIsSubmitting(false);
      setShowSuccess(true);

      setTimeout(() => {
        setShowSuccess(false);
        closeOrderModal();
        toast.success("Trade Opened! 🎯", {
          description: `${side} ${quantity} x ${selectedOption.instrumentName} @ ₹${executionPrice.toFixed(2)}`,
        });
      }, 1200);

    } catch (e: any) {
      setIsSubmitting(false);
      // ✅ Show explicit backend error message if available
      const msg = e.message || "Could not place order. Check connection.";
      toast.error("Order Failed", { description: msg });
    }
  };

  const handleClose = () => {
    if (!isSubmitting) {
      closeOrderModal();
      setShowSuccess(false);
    }
  };

  if (!selectedOption) return null;

  return (
    <AnimatePresence>
      {orderModalOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
            onClick={handleClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, x: 100 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 100 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-border bg-card shadow-elevated"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border p-4">
              <div>
                <h2 className="text-lg font-semibold text-foreground">Place Order</h2>
                <p className="text-sm text-muted-foreground">{selectedOption.instrumentName}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={handleClose} disabled={isSubmitting}>
                <X className="h-5 w-5" />
              </Button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
              <AnimatePresence mode="wait">
                {showSuccess ? (
                  <motion.div
                    key="success"
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={{ scale: 0.8, opacity: 0 }}
                    className="flex h-full flex-col items-center justify-center"
                  >
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring", damping: 10, stiffness: 200 }}
                      className="mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-profit/20"
                    >
                      <Check className="h-12 w-12 text-profit" />
                    </motion.div>
                    <motion.h3
                      initial={{ y: 20, opacity: 0 }}
                      animate={{ y: 0, opacity: 1 }}
                      transition={{ delay: 0.2 }}
                      className="text-2xl font-bold text-foreground"
                    >
                      Order Executed! 🎯
                    </motion.h3>
                    <motion.p
                      initial={{ y: 20, opacity: 0 }}
                      animate={{ y: 0, opacity: 1 }}
                      transition={{ delay: 0.3 }}
                      className="mt-2 text-muted-foreground"
                    >
                      {side} {quantity} x {selectedOption.instrumentName}
                    </motion.p>
                  </motion.div>
                ) : (
                  <motion.div
                    key="form"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="space-y-6"
                  >
                    {/* Live Price Context (Bid/Ask) */}
                    <div className="rounded-lg bg-secondary/50 p-4">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">
                          {side === "BUY" ? "Best Ask (Buy Price)" : "Best Bid (Sell Price)"}
                        </span>
                        {executionPrice > 0 ? (
                          <div className="flex flex-col items-end">
                            <motion.div
                              key={executionPrice}
                              initial={{ scale: 1.1 }}
                              animate={{ scale: 1 }}
                              className="flex items-center gap-2"
                            >
                              <span className={cn("text-2xl font-bold", side === "BUY" ? "text-loss" : "text-profit")}>
                                ₹{executionPrice.toFixed(2)}
                              </span>
                            </motion.div>
                            {/* Show LTP Reference if different */}
                            {Math.abs(executionPrice - liveLtp) > 0.05 && (
                              <span className="text-xs text-muted-foreground">LTP: ₹{liveLtp.toFixed(2)}</span>
                            )}
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <AlertCircle className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm text-muted-foreground">No Quote</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* ✅ AVAILABLE BALANCE */}
                    <div className="rounded-lg border border-border bg-gradient-to-r from-secondary/50 to-transparent p-3">
                      <div className="flex justify-between items-center text-sm">
                        <span className="text-muted-foreground">Available Balance</span>
                        <span className="font-mono font-bold text-foreground">
                          ₹{availableBalance.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                        </span>
                      </div>
                    </div>

                    {/* Existing Position Alert */}
                    {existingPosition && (
                      <div className="rounded-lg border border-streak/30 bg-streak/10 p-3">
                        <div className="flex items-center gap-2 text-sm text-streak">
                          <AlertCircle className="h-4 w-4" />
                          <span>
                            You have an open {existingPosition.side} position of{" "}
                            {existingPosition.quantity} qty @ ₹{existingPosition.entryPrice.toFixed(2)}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Sell Validation Warning */}
                    {side === "SELL" && !canSell && (
                      <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
                        <div className="flex items-center gap-2 text-sm text-destructive">
                          <AlertCircle className="h-4 w-4" />
                          <span>
                            {existingPosition
                              ? `You can only sell ${existingPosition.quantity} shares (you're trying to sell ${quantity})`
                              : "You don't own any shares of this instrument"}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* ✅ BUY BALANCE VALIDATION */}
                    {side === "BUY" && !canBuy && (
                      <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3">
                        <div className="flex items-center gap-2 text-sm text-destructive">
                          <AlertCircle className="h-4 w-4" />
                          <span>Insufficient balance for this trade</span>
                        </div>
                      </div>
                    )}

                    {/* Buy/Sell Toggle */}
                    <div>
                      <Label className="mb-3 block text-sm text-muted-foreground">Side</Label>
                      <div className="grid grid-cols-2 gap-3">
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => setSide("BUY")}
                          className={cn(
                            "h-14 text-lg font-semibold transition-all",
                            side === "BUY"
                              ? "bg-profit/20 text-profit ring-2 ring-profit"
                              : "bg-secondary text-muted-foreground hover:bg-secondary/80"
                          )}
                        >
                          BUY
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => setSide("SELL")}
                          disabled={!existingPosition}
                          className={cn(
                            "h-14 text-lg font-semibold transition-all",
                            side === "SELL"
                              ? "bg-loss/20 text-loss ring-2 ring-loss"
                              : "bg-secondary text-muted-foreground hover:bg-secondary/80",
                            !existingPosition && "opacity-50 cursor-not-allowed"
                          )}
                        >
                          SELL
                        </Button>
                      </div>
                    </div>

                    {/* Order Type */}
                    <div>
                      <Label className="mb-3 block text-sm text-muted-foreground">Order Type</Label>
                      <div className="grid grid-cols-2 gap-3">
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => setOrderType("MARKET")}
                          className={cn(
                            "h-12 font-semibold transition-all",
                            orderType === "MARKET"
                              ? "bg-primary/20 text-primary ring-2 ring-primary"
                              : "bg-secondary text-muted-foreground hover:bg-secondary/80"
                          )}
                        >
                          MARKET
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          onClick={() => setOrderType("LIMIT")}
                          className={cn(
                            "h-12 font-semibold transition-all",
                            orderType === "LIMIT"
                              ? "bg-primary/20 text-primary ring-2 ring-primary"
                              : "bg-secondary text-muted-foreground hover:bg-secondary/80"
                          )}
                        >
                          LIMIT
                        </Button>
                      </div>
                    </div>

                    {/* Limit Price Input */}
                    {orderType === "LIMIT" && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                      >
                        <Label htmlFor="limitPrice" className="mb-2 block text-sm text-muted-foreground">
                          Limit Price
                        </Label>
                        <Input
                          id="limitPrice"
                          type="number"
                          step="0.05"
                          value={limitPrice}
                          onChange={(e) => setLimitPrice(e.target.value)}
                          className="h-12 text-lg font-mono"
                          placeholder="Enter limit price"
                        />
                      </motion.div>
                    )}

                    {/* Lots Input */}
                    <div>
                      <Label htmlFor="lots" className="mb-2 block text-sm text-muted-foreground">
                        Lots (1 Lot = {lotSize} qty) {/* ✅ DYNAMIC LOT SIZE */}
                      </Label>
                      <div className="flex items-center gap-3">
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          onClick={() => setLots(Math.max(1, lots - 1))}
                          className="h-12 w-12"
                        >
                          -
                        </Button>
                        <Input
                          id="lots"
                          type="number"
                          min={1}
                          max={20}
                          value={lots}
                          onChange={(e) => setLots(Math.max(1, Math.min(20, parseInt(e.target.value) || 1)))}
                          className="h-12 text-center text-lg font-mono"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          onClick={() => setLots(Math.min(20, lots + 1))}
                          className="h-12 w-12"
                        >
                          +
                        </Button>
                      </div>

                      {/* Available / Max Helper */}
                      <div className="mt-2 flex justify-between items-center text-xs">
                        <p className="text-muted-foreground">
                          Quantity: {quantity} ({lots} lot{lots > 1 ? "s" : ""})
                        </p>
                        {side === "SELL" && existingPosition && (
                          <div className="flex items-center gap-2">
                            <span className="text-muted-foreground">
                              Avail: {existingPosition.quantity} ({Math.floor(existingPosition.quantity / lotSize)} lots)
                            </span>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-5 px-2 text-[10px] bg-secondary hover:bg-secondary/80"
                              onClick={() => {
                                // Calculate max lots
                                const maxLots = Math.floor(existingPosition.quantity / lotSize);
                                if (maxLots >= 1) setLots(maxLots);
                              }}
                            >
                              MAX
                            </Button>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Order Summary */}
                    <div className="rounded-lg border border-border bg-secondary/30 p-4 space-y-3">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Instrument</span>
                        <span className="font-semibold text-foreground">
                          {selectedOption.instrumentName}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Order Type</span>
                        <span className="font-semibold text-foreground">
                          {orderType}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Price</span>
                        <span className="font-mono font-semibold text-foreground">
                          ₹{executionPrice.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Quantity</span>
                        <span className="font-mono text-foreground">{quantity}</span>
                      </div>
                      <div className="border-t border-border pt-3">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Order Value</span>
                          <span className="font-mono font-bold text-foreground">
                            ₹{orderValue.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      </div>
                      {side === "BUY" && (
                        <div className="flex justify-between text-sm bg-primary/10 p-2 rounded">
                          <span className="text-foreground font-semibold">Amount Required</span>
                          <span className="font-mono font-bold text-primary">
                            ₹{marginRequired.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      )}
                      {side === "SELL" && (
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Margin Required</span>
                          <span className="font-mono text-foreground">
                            ₹{marginRequired.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Footer */}
            {!showSuccess && (
              <div className="border-t border-border p-4">
                <Button
                  type="button"
                  onClick={handleSubmit}
                  disabled={isSubmitting || liveLtp === 0 || (side === "SELL" && !canSell) || (side === "BUY" && !canBuy)}
                  className={cn(
                    "w-full h-14 text-lg font-semibold transition-all",
                    side === "BUY"
                      ? "bg-profit hover:bg-profit/90 text-background"
                      : "bg-loss hover:bg-loss/90 text-foreground"
                  )}
                >
                  {isSubmitting ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : liveLtp === 0 ? (
                    "No LTP Available"
                  ) : side === "SELL" && !canSell ? (
                    "Cannot Sell"
                  ) : side === "BUY" && !canBuy ? (
                    "Insufficient Balance"
                  ) : existingPosition && side === "SELL" && existingPosition.side === "BUY" ? (
                    `CLOSE POSITION @ ₹${liveLtp.toFixed(2)}`
                  ) : (
                    `${side} ${quantity} @ ₹${executionPrice.toFixed(2)}`
                  )}
                </Button>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
