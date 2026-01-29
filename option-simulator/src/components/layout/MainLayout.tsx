import React from "react";
import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  LineChart,
  Briefcase,
  User,
  LogOut,
  TrendingUp,
  Menu,
  X,
  Flame,
  Trophy,
  Target,
  Home,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { useAuthStore } from "@/stores/authStore";
import { useTradeStore } from "@/stores/tradeStore";
import { useMarketStore } from "@/stores/marketStore";
import { useUIStore } from "@/stores/uiStore";
import { useBrokerStore } from "@/stores/brokerStore";
import { BrokerStatus } from "@/types/trading";
import { Button } from "@/components/ui/button";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/trade", label: "Trade", icon: LineChart },
  { path: "/portfolio", label: "Portfolio", icon: Briefcase },
  { path: "/account", label: "Account", icon: User },
  { path: "/", label: "Home", icon: Home },
];

interface MainLayoutProps {
  children: React.ReactNode;
}

export const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const location = useLocation();
  const { logout } = useAuth();
  const { user } = useAuthStore();
  const { todayTradeCount, winRate, streak } = useTradeStore();
  const { netPnl } = useMarketStore();
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { status: brokerStatus } = useBrokerStore();

  console.log("MainLayout render:", { sidebarOpen, user, netPnl, location, streak, brokerStatus });

  return (
    <div className="flex min-h-screen bg-background">
      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-background/80 backdrop-blur-sm md:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <motion.aside
        className={cn(
          "fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-border bg-card transition-all duration-300",
          sidebarOpen ? "w-[260px] translate-x-0" : "w-[80px] -translate-x-full md:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between border-b border-border px-4">
          {sidebarOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-2"
            >
              <TrendingUp className="h-8 w-8 text-primary" />
              <span className="text-xl font-bold text-foreground">OptionSim</span>
            </motion.div>
          )}
          <Button variant="ghost" size="icon" onClick={toggleSidebar} className="ml-auto">
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>

        {/* Gamification Stats */}
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="border-b border-border p-4"
          >
            <div className="grid grid-cols-3 gap-2">
              <div className="flex flex-col items-center rounded-lg bg-secondary/50 p-2">
                <Flame className="h-4 w-4 text-streak" />
                <span className="mt-1 text-lg font-bold text-foreground">{streak}</span>
                <span className="text-[10px] text-muted-foreground">Streak</span>
              </div>
              <div className="flex flex-col items-center rounded-lg bg-secondary/50 p-2">
                <Target className="h-4 w-4 text-primary" />
                <span className="mt-1 text-lg font-bold text-foreground">{todayTradeCount}</span>
                <span className="text-[10px] text-muted-foreground">Today</span>
              </div>
              <div className="flex flex-col items-center rounded-lg bg-secondary/50 p-2">
                <Trophy className="h-4 w-4 text-xp" />
                <span className="mt-1 text-lg font-bold text-foreground">{winRate}%</span>
                <span className="text-[10px] text-muted-foreground">Win</span>
              </div>
            </div>
          </motion.div>
        )}

        {/* Navigation */}
        <nav className="flex-1 p-4">
          <ul className="space-y-2">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              // ✅ FIX: Disable Trade tab when broker is not connected
              const isTradeDisabled = item.path === "/trade" && brokerStatus !== BrokerStatus.TOKEN_VALID;
              
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    onClick={(e) => {
                      if (isTradeDisabled) {
                        e.preventDefault();
                        alert("Please connect your Upstox broker to trade");
                      }
                    }}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all",
                      isTradeDisabled && "pointer-events-none opacity-50 cursor-not-allowed",
                      isActive
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                    )}
                    title={isTradeDisabled ? "Broker not connected. Please reconnect your Upstox account." : ""}
                  >
                    <item.icon className={cn("h-5 w-5", !sidebarOpen && "mx-auto")} />
                    {sidebarOpen && <span>{item.label}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* User & Logout */}
        <div className="border-t border-border p-4">
          {sidebarOpen && user && (
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/20 text-sm font-bold text-primary">
                {user.name?.charAt(0) || user.email?.charAt(0) || "U"}
              </div>
              <div className="flex-1 overflow-hidden">
                <p className="truncate text-sm font-medium text-foreground">{user.name}</p>
                <p className="truncate text-xs text-muted-foreground">{user.email}</p>
              </div>
            </div>
          )}
          <Button
            variant="ghost"
            className={cn(
              "w-full justify-start text-muted-foreground hover:text-destructive",
              !sidebarOpen && "justify-center"
            )}
            onClick={logout}
          >
            <LogOut className="h-5 w-5" />
            {sidebarOpen && <span className="ml-3">Logout</span>}
          </Button>
        </div>
      </motion.aside>

      {/* Main Content */}
      <main
        className={cn(
          "flex-1 transition-all duration-300 w-full",
          "md:ml-[80px] md:w-auto",
          sidebarOpen && "lg:ml-[260px]"
        )}
      >
        {/* Top Bar */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/95 px-3 md:px-6 backdrop-blur supports-[backdrop-filter]:bg-background/60">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSidebar}
              className="md:hidden"
            >
              <Menu className="h-5 w-5" />
            </Button>
            <h1 className="text-base md:text-lg font-semibold text-foreground truncate">
              {navItems.find((item) => item.path === location.pathname)?.label || "Dashboard"}
            </h1>
          </div>

          {/* Net PnL Display */}
          <div className="flex items-center gap-2 md:gap-4">
            <div className="flex items-center gap-1 md:gap-2 rounded-lg bg-secondary px-2 md:px-4 py-1 md:py-2">
              <span className="text-xs md:text-sm text-muted-foreground hidden sm:inline">Net P&L</span>
              <span
                className={cn(
                  "text-sm md:text-lg font-bold tabular-nums",
                  netPnl >= 0 ? "pnl-profit" : "pnl-loss"
                )}
              >
                {netPnl >= 0 ? "+" : ""}₹{netPnl.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>
        </header>

        <div className="p-3 md:p-6">{children}</div>
      </main>
    </div>
  );
};
