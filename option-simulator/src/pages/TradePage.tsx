import React, { useEffect } from "react";
import { OptionChain } from "@/components/trading/OptionChain";
import { TradeManager } from "@/components/trading/TradeManager";
import { OrderModal } from "@/components/trading/OrderModal";
import { RiskCalculator } from "@/components/trading/RiskCalculator";
import { MainLayout } from "@/components/layout/MainLayout";
import { useBrokerStore } from "@/stores/brokerStore";
import { useMarketStore } from "@/stores/marketStore";
import { useAuthStore } from "@/stores/authStore";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Link2 } from "lucide-react";
import { logger } from "@/lib/logger";

const COMPONENT_NAME = "TradePage";

export default function TradePage() {
  const { status: brokerStatus, isLoading, checkConnection } = useBrokerStore();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const { user } = useAuthStore();

  // Get Market Data for Header (Must be called before any early returns)
  const { selectedInstrument, ltpMap, optionChain } = useMarketStore();

  // Force refresh broker status after OAuth callback
  useEffect(() => {
    const brokerConnected = searchParams.get('broker_connected');
    if (brokerConnected) {
      logger.info(COMPONENT_NAME, "Broker OAuth callback detected, refreshing status");
      checkConnection().then(() => {
        // Clean up URL parameter
        navigate('/trade', { replace: true });
      });
    }
  }, [searchParams, checkConnection, navigate]);

  const marketStatus = optionChain?.market_status || "OPEN";

  // Calculate Spot Price (same logic as useOptionChainData)
  const currentSpotPrice = marketStatus === "CLOSED"
    ? (optionChain?.spot_price || 0)
    : ((selectedInstrument && ltpMap[selectedInstrument?.key]) || optionChain?.spot_price || 0);

  if (isLoading) {
    return (
      <MainLayout>
        <div className="flex h-[50vh] items-center justify-center">
          <p className="text-muted-foreground">Checking broker connection...</p>
        </div>
      </MainLayout>
    )
  }

  if (brokerStatus !== "TOKEN_VALID") {
    return (
      <MainLayout>
        <div className="flex flex-col items-center justify-center space-y-4 md:space-y-6 py-10 md:py-20 border-2 border-dashed border-muted rounded-xl bg-muted/20 m-3 md:m-6">
          <div className="rounded-full bg-secondary p-4 md:p-6">
            <Link2 className="h-8 w-8 md:h-12 md:w-12 text-muted-foreground opacity-50" />
          </div>
          <div className="text-center space-y-2 px-4">
            <h2 className="text-xl md:text-2xl font-bold text-destructive">Trading Access Locked</h2>
            <p className="text-sm md:text-base text-muted-foreground max-w-md mx-auto">
              Live market data and trading execution are disabled.
              Please connect your Upstox account to unlock this page.
            </p>
          </div>
          <Button onClick={() => navigate("/account")} variant="outline" size="lg" className="text-sm md:text-base">
            Go to Account Settings
          </Button>
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className="space-y-3 md:space-y-6">
        {/* Toolbar */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-4">
          <div className="flex items-center gap-2 md:gap-4 w-full sm:w-auto">
            <h2 className="text-base md:text-xl font-bold text-foreground">{selectedInstrument?.name || "NIFTY 50"}</h2>
            <div className="flex items-center gap-1 md:gap-2 rounded-lg bg-secondary px-2 md:px-3 py-1 md:py-1.5">
              <span className="text-lg md:text-2xl font-bold tabular-nums text-foreground">
                {currentSpotPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              {/* Change % logic requires previous close which isn't available yet - hiding to avoid misinformation */}
              {/* <span className="text-xs md:text-sm font-medium text-profit">+0.00</span> */}
            </div>
          </div>
          <div className="flex items-center gap-2 md:gap-4 w-full sm:w-auto justify-between sm:justify-end">
            <div className="bg-primary/10 px-3 md:px-4 py-1.5 md:py-2 rounded-lg border border-primary/20 hidden lg:block">
              <span className="text-xs text-muted-foreground uppercase font-bold mr-2">Virtual Balance</span>
              <span className="text-base md:text-lg font-mono font-bold text-primary">
                ₹{user?.virtual_balance?.toLocaleString('en-IN') || '50,000.00'}
              </span>
            </div>
            <RiskCalculator />
          </div>
        </div>
      </div>
      {/* Main Trading Area */}
      <div className="flex-1 overflow-hidden p-2 md:p-4 pt-2">
        <div className="grid h-full grid-cols-1 gap-3 md:gap-4 lg:grid-cols-12">

          {/* Left Panel: Option Chain (Wider) */}
          <div className="col-span-1 lg:col-span-9 h-[60vh] lg:h-full min-h-0">
            <OptionChain />
          </div>

          {/* Right Panel: Open Positions & Trades (Narrower) */}
          <div className="col-span-1 lg:col-span-3 h-[40vh] lg:h-full min-h-0 flex flex-col gap-3 md:gap-4">
            <div className="h-full lg:h-1/2 flex-1 min-h-0">
              <TradeManager />
            </div>
          </div>

        </div>
      </div>

      {/* Order Modal */}
      <OrderModal />
    </MainLayout>
  );
}
