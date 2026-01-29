import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Calculator, X, ArrowRight } from "lucide-react";
import { useUIStore } from "@/stores/uiStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export const RiskCalculator: React.FC = () => {
  const { riskCalculatorOpen, setRiskCalculatorOpen } = useUIStore();
  const [entry, setEntry] = useState<string>("");
  const [target, setTarget] = useState<string>("");
  const [stoploss, setStoploss] = useState<string>("");
  const [quantity, setQuantity] = useState<string>("50");
  const [result, setResult] = useState<{
    riskRewardRatio: number;
    potentialProfit: number;
    potentialLoss: number;
    riskPercent: number;
    rewardPercent: number;
  } | null>(null);
  const [errors, setErrors] = useState<{
    entry?: string;
    target?: string;
    stoploss?: string;
    quantity?: string;
  }>({});

  const validateAndCalculate = () => {
    const newErrors: typeof errors = {};
    
    const entryNum = parseFloat(entry);
    const targetNum = parseFloat(target);
    const stoplossNum = parseFloat(stoploss);
    const quantityNum = parseInt(quantity, 10);
    
    if (!entry || isNaN(entryNum) || entryNum <= 0) {
      newErrors.entry = "Enter valid entry price";
    }
    if (!target || isNaN(targetNum) || targetNum <= 0) {
      newErrors.target = "Enter valid target";
    }
    if (!stoploss || isNaN(stoplossNum) || stoplossNum <= 0) {
      newErrors.stoploss = "Enter valid stop loss";
    }
    if (!quantity || isNaN(quantityNum) || quantityNum <= 0) {
      newErrors.quantity = "Enter valid quantity";
    }
    
    setErrors(newErrors);
    
    if (Object.keys(newErrors).length > 0) {
      return;
    }
    
    // Calculate risk/reward
    const risk = Math.abs(entryNum - stoplossNum);
    const reward = Math.abs(targetNum - entryNum);
    const riskRewardRatio = risk > 0 ? reward / risk : 0;
    const riskPercent = ((entryNum - stoplossNum) / entryNum) * 100;
    const rewardPercent = ((targetNum - entryNum) / entryNum) * 100;

    setResult({
      riskRewardRatio,
      potentialProfit: reward * quantityNum,
      potentialLoss: risk * quantityNum,
      riskPercent: Math.abs(riskPercent),
      rewardPercent: Math.abs(rewardPercent),
    });
  };

  const handleClose = () => {
    setRiskCalculatorOpen(false);
    setResult(null);
    setErrors({});
  };

  const resetForm = () => {
    setEntry("");
    setTarget("");
    setStoploss("");
    setQuantity("50");
    setResult(null);
    setErrors({});
  };

  return (
    <>
      {/* Trigger Button */}
      <Button
        variant="secondary"
        size="sm"
        onClick={() => setRiskCalculatorOpen(true)}
        className="gap-2"
      >
        <Calculator className="h-4 w-4" />
        R:R Calculator
      </Button>

      <AnimatePresence>
        {riskCalculatorOpen && (
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
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="trade-card p-6">
                {/* Header */}
                <div className="mb-6 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/20">
                      <Calculator className="h-5 w-5 text-primary" />
                    </div>
                    <h2 className="text-lg font-semibold text-foreground">Risk/Reward Calculator</h2>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleClose}
                    type="button"
                  >
                    <X className="h-5 w-5" />
                  </Button>
                </div>

                {/* Form */}
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor="entry" className="text-xs text-muted-foreground">
                        Entry Price
                      </Label>
                      <Input
                        id="entry"
                        type="number"
                        step="0.01"
                        value={entry}
                        onChange={(e) => setEntry(e.target.value)}
                        className={cn("mt-1 font-mono", errors.entry && "border-destructive")}
                        placeholder="100"
                      />
                      {errors.entry && (
                        <p className="mt-1 text-xs text-destructive">{errors.entry}</p>
                      )}
                    </div>
                    <div>
                      <Label htmlFor="quantity" className="text-xs text-muted-foreground">
                        Quantity
                      </Label>
                      <Input
                        id="quantity"
                        type="number"
                        value={quantity}
                        onChange={(e) => setQuantity(e.target.value)}
                        className={cn("mt-1 font-mono", errors.quantity && "border-destructive")}
                        placeholder="50"
                      />
                      {errors.quantity && (
                        <p className="mt-1 text-xs text-destructive">{errors.quantity}</p>
                      )}
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor="target" className="text-xs text-muted-foreground">
                        Target Price
                      </Label>
                      <Input
                        id="target"
                        type="number"
                        step="0.01"
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                        className={cn("mt-1 font-mono", errors.target && "border-destructive")}
                        placeholder="120"
                      />
                      {errors.target && (
                        <p className="mt-1 text-xs text-destructive">{errors.target}</p>
                      )}
                    </div>
                    <div>
                      <Label htmlFor="stoploss" className="text-xs text-muted-foreground">
                        Stop Loss
                      </Label>
                      <Input
                        id="stoploss"
                        type="number"
                        step="0.01"
                        value={stoploss}
                        onChange={(e) => setStoploss(e.target.value)}
                        className={cn("mt-1 font-mono", errors.stoploss && "border-destructive")}
                        placeholder="90"
                      />
                      {errors.stoploss && (
                        <p className="mt-1 text-xs text-destructive">{errors.stoploss}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Button type="button" onClick={validateAndCalculate} className="flex-1">
                      Calculate
                    </Button>
                    <Button type="button" variant="outline" onClick={resetForm}>
                      Reset
                    </Button>
                  </div>
                </div>

                {/* Results */}
                <AnimatePresence>
                  {result && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-6 overflow-hidden"
                    >
                      <div className="rounded-lg border border-border bg-secondary/30 p-4">
                        {/* R:R Ratio */}
                        <div className="mb-4 text-center">
                          <p className="text-sm text-muted-foreground">Risk : Reward</p>
                          <div className="mt-1 flex items-center justify-center gap-3">
                            <span className="text-2xl font-bold text-loss">1</span>
                            <ArrowRight className="h-5 w-5 text-muted-foreground" />
                            <span className="text-2xl font-bold text-profit">
                              {result.riskRewardRatio.toFixed(2)}
                            </span>
                          </div>
                        </div>

                        {/* Details */}
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div className="rounded-lg bg-profit/10 p-3 text-center">
                            <p className="text-muted-foreground">Potential Profit</p>
                            <p className="mt-1 font-mono text-lg font-bold text-profit">
                              ₹{result.potentialProfit.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                            </p>
                            <p className="text-xs text-profit">
                              +{result.rewardPercent.toFixed(2)}%
                            </p>
                          </div>
                          <div className="rounded-lg bg-loss/10 p-3 text-center">
                            <p className="text-muted-foreground">Potential Loss</p>
                            <p className="mt-1 font-mono text-lg font-bold text-loss">
                              ₹{result.potentialLoss.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                            </p>
                            <p className="text-xs text-loss">
                              -{result.riskPercent.toFixed(2)}%
                            </p>
                          </div>
                        </div>

                        {/* Verdict */}
                        <div
                          className={cn(
                            "mt-4 rounded-lg p-3 text-center",
                            result.riskRewardRatio >= 2
                              ? "bg-profit/20"
                              : result.riskRewardRatio >= 1
                              ? "bg-streak/20"
                              : "bg-loss/20"
                          )}
                        >
                          <p
                            className={cn(
                              "font-semibold",
                              result.riskRewardRatio >= 2
                                ? "text-profit"
                                : result.riskRewardRatio >= 1
                                ? "text-streak"
                                : "text-loss"
                            )}
                          >
                            {result.riskRewardRatio >= 2
                              ? "✓ Good Risk/Reward"
                              : result.riskRewardRatio >= 1
                              ? "⚡ Moderate Risk"
                              : "⚠ High Risk Trade"}
                          </p>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
};
