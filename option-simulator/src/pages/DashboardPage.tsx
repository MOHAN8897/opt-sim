import React from "react";
import { motion } from "framer-motion";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  Target,
  Flame,
  Trophy,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { MainLayout } from "@/components/layout/MainLayout";
import { useTradeStore } from "@/stores/tradeStore";
import { useMarketStore } from "@/stores/marketStore";
import { useAuthStore } from "@/stores/authStore";
import { cn } from "@/lib/utils";

const StatCard: React.FC<{
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  trend?: "up" | "down" | null;
  delay?: number;
}> = ({ title, value, subtitle, icon, trend, delay = 0 }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay }}
    className="trade-card p-6"
  >
    <div className="flex items-start justify-between">
      <div>
        <p className="text-sm text-muted-foreground">{title}</p>
        <p className="mt-2 text-3xl font-bold text-foreground">{value}</p>
        {subtitle && (
          <p
            className={cn(
              "mt-1 flex items-center gap-1 text-sm",
              trend === "up" ? "text-profit" : trend === "down" ? "text-loss" : "text-muted-foreground"
            )}
          >
            {trend === "up" && <ArrowUpRight className="h-4 w-4" />}
            {trend === "down" && <ArrowDownRight className="h-4 w-4" />}
            {subtitle}
          </p>
        )}
      </div>
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
        {icon}
      </div>
    </div>
  </motion.div>
);

const DashboardPage: React.FC = () => {
  const { openTrades, tradeHistory, todayTradeCount, winRate, streak, fetchTrades } = useTradeStore();
  const { netPnl } = useMarketStore();
  const { user, isAuthenticated } = useAuthStore();

  React.useEffect(() => {
    if (isAuthenticated) {
      fetchTrades();
    }
  }, [isAuthenticated, fetchTrades]);

  const todayPnl = tradeHistory
    .filter((t) => {
      const today = new Date().toDateString();
      return new Date(t.closedAt || "").toDateString() === today;
    })
    .reduce((acc, t) => acc + (t.pnl || 0), 0);

  return (
    <MainLayout>
      <div className="space-y-6">
        {/* Welcome Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div>
            <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
            <p className="mt-1 text-muted-foreground">
              Track your trading performance and metrics
            </p>
          </div>
        </motion.div>

        {/* Stats Grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Account Balance"
            value={`₹${user?.virtual_balance?.toLocaleString("en-IN") || '50,000'}`}
            subtitle="Available Funds"
            icon={<Wallet className="h-6 w-6 text-primary" />}
            delay={0.1}
          />
          <StatCard
            title="Net P&L"
            value={`${netPnl >= 0 ? "+" : ""}₹${netPnl.toLocaleString("en-IN")}`}
            subtitle="Unrealized"
            icon={<TrendingUp className="h-6 w-6 text-primary" />} // Changed Icon to distinguish
            trend={netPnl >= 0 ? "up" : "down"}
            delay={0.1}
          />
          <StatCard
            title="Today's P&L"
            value={`${todayPnl >= 0 ? "+" : ""}₹${todayPnl.toLocaleString("en-IN")}`}
            subtitle="Realized"
            icon={<BarChart3 className="h-6 w-6 text-primary" />}
            trend={todayPnl >= 0 ? "up" : todayPnl < 0 ? "down" : null}
            delay={0.2}
          />
          <StatCard
            title="Win Rate"
            value={`${winRate}%`}
            subtitle="Last 30 trades"
            icon={<Trophy className="h-6 w-6 text-xp" />}
            delay={0.3}
          />
          <StatCard
            title="Streak"
            value={`${streak}`}
            subtitle="Consecutive wins"
            icon={<Flame className="h-6 w-6 text-streak" />}
            delay={0.4}
          />
        </div>

        {/* Activity Section */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Open Positions Summary */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.5 }}
            className="trade-card p-6"
          >
            <h3 className="mb-4 text-lg font-semibold text-foreground">Open Positions</h3>
            {openTrades.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Target className="mb-3 h-10 w-10 text-muted-foreground" />
                <p className="text-muted-foreground">No open positions</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Start trading from the Trade page
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {openTrades.slice(0, 3).map((trade) => (
                  <div
                    key={trade.id}
                    className="flex items-center justify-between rounded-lg bg-secondary/50 p-3"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          "flex h-8 w-8 items-center justify-center rounded-lg",
                          trade.optionType === "CE" ? "bg-call/20" : "bg-put/20"
                        )}
                      >
                        {trade.side === "BUY" ? (
                          <TrendingUp
                            className={cn(
                              "h-4 w-4",
                              trade.optionType === "CE" ? "text-call" : "text-put"
                            )}
                          />
                        ) : (
                          <TrendingDown
                            className={cn(
                              "h-4 w-4",
                              trade.optionType === "CE" ? "text-call" : "text-put"
                            )}
                          />
                        )}
                      </div>
                      <div>
                        <p className="font-medium text-foreground">{trade.instrumentName}</p>
                        <p className="text-xs text-muted-foreground">
                          {trade.side} · {trade.quantity} qty
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-mono font-medium text-foreground">
                        ₹{trade.entryPrice.toFixed(2)}
                      </p>
                    </div>
                  </div>
                ))}
                {openTrades.length > 3 && (
                  <p className="text-center text-sm text-muted-foreground">
                    +{openTrades.length - 3} more positions
                  </p>
                )}
              </div>
            )}
          </motion.div>

          {/* Today's Activity */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.6 }}
            className="trade-card p-6"
          >
            <h3 className="mb-4 text-lg font-semibold text-foreground">Today's Activity</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg bg-secondary/50 p-4 text-center">
                <p className="text-3xl font-bold text-foreground">{todayTradeCount}</p>
                <p className="mt-1 text-sm text-muted-foreground">Trades Today</p>
              </div>
              <div className="rounded-lg bg-secondary/50 p-4 text-center">
                <p className="text-3xl font-bold text-foreground">{openTrades.length}</p>
                <p className="mt-1 text-sm text-muted-foreground">Open Positions</p>
              </div>
            </div>

            {/* Progress Bar */}
            <div className="mt-6">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Daily Goal Progress</span>
                <span className="font-medium text-foreground">
                  {Math.min(todayTradeCount, 10)}/10 trades
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-secondary">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min((todayTradeCount / 10) * 100, 100)}%` }}
                  transition={{ delay: 0.8, duration: 0.5 }}
                  className="h-full bg-gradient-to-r from-primary to-accent"
                />
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </MainLayout>
  );
};

export default DashboardPage;
