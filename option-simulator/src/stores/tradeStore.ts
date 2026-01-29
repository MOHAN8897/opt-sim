import { create } from "zustand";
import { logger, logStore } from "@/lib/logger";

function getCorrelationId(base?: string) {
  if (base) return base;
  return 'corr_' + Math.random().toString(36).slice(2) + Date.now();
}
import { useAuthStore } from "./authStore";

const STORE_NAME = "TradeStore";

export interface Trade {
  id: string;
  instrumentKey: string;
  instrumentName: string; // Original Key or Name
  tradingSymbol?: string; // Friendly Name (e.g. BANKNIFTY ...)
  optionType: "CE" | "PE";
  strike: number;
  side: "BUY" | "SELL";
  quantity: number;
  entryPrice: number;
  exitPrice?: number;
  status: "OPEN" | "CLOSED";
  createdAt: string;
  closedAt?: string;
  pnl?: number;
  expiryDate?: string;
}

interface TradeState {
  openTrades: Trade[];
  tradeHistory: Trade[];
  todayTradeCount: number;
  winRate: number;
  streak: number;
  setOpenTrades: (trades: Trade[]) => void;
  fetchTrades: () => Promise<void>;
  fetchHistory: () => Promise<void>;
  placeTrade: (tradeDetails: any) => Promise<Trade>;
  addTrade: (trade: Trade) => void;
  updateTrade: (trade: Trade) => void;
  closeTrade: (tradeId: string, exitPrice: number) => Promise<void>;
  setTradeHistory: (trades: Trade[]) => void;
  setStats: (stats: { todayTradeCount: number; winRate: number; streak: number }) => void;
  reset: () => void;
}

export const useTradeStore = create<TradeState>((set, get) => ({
  openTrades: [],
  tradeHistory: [],
  todayTradeCount: 0,
  winRate: 0,
  streak: 0,

  setOpenTrades: (trades) => {
    logger.info(STORE_NAME, `Setting ${trades.length} open trades`, undefined, getCorrelationId());
    set({ openTrades: trades });
  },

  fetchTrades: async () => {
    // Rely on HttpOnly cookie
    try {
      const res = await fetch("/api/orders/trades", {
        credentials: 'include'  // Use cookies instead of Bearer token
      });
      if (res.ok) {
        const trades = await res.json();
        // Map backend Trade model to frontend interface
        const mappedTrades = trades.map((t: any) => ({
          id: t.id.toString(),
          instrumentKey: t.instrument_key,
          instrumentName: (t.name && t.strike_price && t.option_type)
            ? `${t.name} ${t.strike_price} ${t.option_type}`
            : (t.name || t.trading_symbol || t.instrument_key),
          tradingSymbol: t.trading_symbol,
          optionType: t.option_type || (t.instrument_key.includes('CE') ? 'CE' : 'PE'),
          strike: t.strike_price || 0,
          side: t.side,
          quantity: t.qty,
          entryPrice: parseFloat(t.entry_price),
          status: t.status,
          createdAt: t.created_at,
          expiryDate: t.expiry_date,
          // ✅ Map Slippage Details
          slippage: t.slippage ? parseFloat(t.slippage) : undefined,
          expectedPrice: t.expected_price ? parseFloat(t.expected_price) : undefined
        }));
        set({ openTrades: mappedTrades });
        logger.info(STORE_NAME, `Fetched ${mappedTrades.length} open trades`, undefined, getCorrelationId());
      }

      // Also fetch history
      await get().fetchHistory();

    } catch (e) {
      logger.error(STORE_NAME, "Failed to fetch trades", e, getCorrelationId());
    }
  },

  fetchHistory: async () => {
    try {
      const res = await fetch("/api/orders/trades/history", {
        credentials: 'include'
      });
      if (res.ok) {
        const trades = await res.json();
        const mappedTrades = trades.map((t: any) => ({
          id: t.id.toString(),
          instrumentKey: t.instrument_key,
          instrumentName: (t.name && t.strike_price && t.option_type)
            ? `${t.name} ${t.strike_price} ${t.option_type}`
            : (t.name || t.trading_symbol || t.instrument_key),
          tradingSymbol: t.trading_symbol,
          optionType: t.option_type || (t.instrument_key.includes('CE') ? 'CE' : 'PE'),
          strike: t.strike_price || 0,
          side: t.side,
          quantity: t.qty,
          entryPrice: parseFloat(t.entry_price),
          exitPrice: t.exit_price ? parseFloat(t.exit_price) : undefined,
          status: t.status,
          createdAt: t.created_at,
          closedAt: t.closed_at,
          pnl: t.realized_pnl ? parseFloat(t.realized_pnl) : undefined,
          expiryDate: t.expiry_date
        }));
        // Calculate Stats
        const today = new Date().toDateString();
        const todaysTrades = mappedTrades.filter((t: any) =>
          new Date(t.closedAt || "").toDateString() === today
        );
        const todayCount = todaysTrades.length;

        // Calculate Win Rate (Last 30 trades)
        const last30 = mappedTrades.slice(0, 30);
        const wins = last30.filter((t: any) => (t.pnl || 0) > 0).length;
        const totalClosed = last30.length;
        const winRate = totalClosed > 0 ? Math.round((wins / totalClosed) * 100) : 0;

        // Calculate Streak
        let currentStreak = 0;
        for (const t of mappedTrades) {
          if ((t.pnl || 0) > 0) currentStreak++;
          else if ((t.pnl || 0) < 0) break; // End of winning streak
        }

        set({
          tradeHistory: mappedTrades,
          todayTradeCount: todayCount,
          winRate: winRate,
          streak: currentStreak
        });
        logger.info(STORE_NAME, `Fetched ${mappedTrades.length} history trades (Today: ${todayCount}, WinRate: ${winRate}%)`, undefined, getCorrelationId());
      }
    } catch (e) {
      logger.error(STORE_NAME, "Failed to fetch trade history", e, getCorrelationId());
    }
  },

  placeTrade: async (tradeDetails: any) => {
    // tradeDetails: { instrumentKey, side, quantity, entryPrice (for LIMIT) }
    try {
      // Create order using new API
      // ✅ FIX: Add trailing slash to prevent 307 Redirect (which kills auth headers)
      const url = "/api/orders/";
      logger.info(STORE_NAME, `Placing trade to ${url}`, tradeDetails, getCorrelationId(tradeDetails?.id));

      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: 'include',
        body: JSON.stringify({
          instrument_key: tradeDetails.instrumentKey,
          side: tradeDetails.side,
          order_type: "MARKET", // Always MARKET for now
          qty: tradeDetails.quantity,
          limit_price: null,
          simulated_price: tradeDetails.entryPrice // ✅ PASS SIMULATED PRICE
        })
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Failed to place order");
      }

      const order = await res.json();
      logger.info(STORE_NAME, `Order ${order.id} created with status: ${order.status}`, order, getCorrelationId(order?.id));

      // If order is FILLED, fetch updated trades
      if (order.status === "FILLED") {
        // Refresh trades to get the newly created trade
        const tradesRes = await fetch("/api/orders/trades", {
          credentials: 'include'
        });

        if (tradesRes.ok) {
          const trades = await tradesRes.json();
          const newTrade = trades[trades.length - 1]; // Get most recent trade

          const mappedTrade: Trade = {
            id: newTrade.id.toString(),
            instrumentKey: newTrade.instrument_key,
            instrumentName: (newTrade.name && newTrade.strike_price && newTrade.option_type)
              ? `${newTrade.name} ${newTrade.strike_price} ${newTrade.option_type}`
              : (newTrade.name || tradeDetails.instrumentName || newTrade.instrument_key),
            tradingSymbol: newTrade.trading_symbol,
            optionType: newTrade.option_type || tradeDetails.optionType || 'CE',
            strike: newTrade.strike_price || tradeDetails.strike || 0,
            side: newTrade.side,
            quantity: newTrade.qty,
            entryPrice: parseFloat(newTrade.entry_price),
            status: newTrade.status,
            createdAt: newTrade.created_at,
            expiryDate: newTrade.expiry_date
          };

          set((state) => ({
            openTrades: [...state.openTrades, mappedTrade],
            todayTradeCount: state.todayTradeCount + 1,
          }));

          // Trigger a full balance refresh since we placed a trade
          useAuthStore.getState().checkAuth();

          return mappedTrade;
        }
      }

      // ✅ FIX: specific error for CANCELLED orders
      if (order.status === "CANCELLED") {
        throw new Error("Order cancelled (likely insufficient balance)");
      }

      // If order is OPEN or PARTIAL, it will fill later
      logger.info(STORE_NAME, `Order ${order.id} is ${order.status}, waiting for fill...`, order, getCorrelationId(order?.id));
      throw new Error("Order placed but not filled yet");

    } catch (e) {
      logger.error(STORE_NAME, "Place Trade Error", e, getCorrelationId());
      throw e;
    }
  },

  addTrade: (trade) => {
    logger.warn(STORE_NAME, "addTrade is deprecated, use placeTrade", undefined, getCorrelationId());
  },

  updateTrade: (trade) => {
    set((state) => ({
      openTrades: state.openTrades.map((t) => (t.id === trade.id ? trade : t))
    }));
  },

  closeTrade: async (tradeId, exitPrice) => {
    try {
      const res = await fetch(`/api/orders/trades/${tradeId}/exit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: 'include',
        body: JSON.stringify({
          exit_price: exitPrice
        })
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Failed to exit trade");
      }

      const data = await res.json();
      logger.info(STORE_NAME, `Exit order created: ${data.exit_order_id}`, data, getCorrelationId(data?.exit_order_id));

      // ✅ BALANCE UPDATE: Update Auth Store with new balance from response
      if (data.new_balance !== undefined) {
        const currentUser = useAuthStore.getState().user;
        if (currentUser) {
          useAuthStore.getState().setUser({
            ...currentUser,
            virtual_balance: data.new_balance
          });
          logger.info(STORE_NAME, `Updated local balance to ₹${data.new_balance}`, data, getCorrelationId());
        }
      }

      // Remove from open trades immediately (optimistic update)
      set((state) => {
        const trade = state.openTrades.find((t) => t.id === tradeId);
        if (!trade) return state;

        const closedTrade: Trade = {
          ...trade,
          exitPrice,
          status: "CLOSED",
          closedAt: new Date().toISOString(),
          pnl: undefined // Will be calculated by backend
        };

        return {
          openTrades: state.openTrades.filter((t) => t.id !== tradeId),
          tradeHistory: [closedTrade, ...state.tradeHistory]
        };
      });

      // Double check balance with a fresh pull (optional but safer)
      // useAuthStore.getState().checkAuth();

    } catch (e) {
      logger.error(STORE_NAME, "Close Trade Error", e, getCorrelationId());
      throw e;
    }
  },

  setTradeHistory: (trades) => {
    logger.info(STORE_NAME, `Setting trade history with ${trades.length} trades`, undefined, getCorrelationId());
    set({ tradeHistory: trades });
  },

  setStats: (stats) => {
    logger.debug(STORE_NAME, 'Updating stats', stats, getCorrelationId());
    set(stats);
  },

  reset: () => {
    logger.info(STORE_NAME, 'Resetting all trade data', undefined, getCorrelationId());
    set({
      openTrades: [],
      tradeHistory: [],
      todayTradeCount: 0,
      winRate: 0,
      streak: 0,
    });
  },
}));
