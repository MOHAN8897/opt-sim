import React, { createContext, useContext, useEffect, useRef, useCallback } from "react";
import ReconnectingWebSocket from "reconnecting-websocket";
import { useAuthStore } from "@/stores/authStore";
import { useMarketStore } from "@/stores/marketStore";
import { useTradeStore, Trade } from "@/stores/tradeStore";
import { toast } from "sonner";
import { logger, logWebSocket } from "@/lib/logger";

const COMPONENT_NAME = "SocketProvider";

interface SocketContextType {
  isConnected: boolean;
}

const SocketContext = createContext<SocketContextType>({ isConnected: false });

export const useSocket = () => useContext(SocketContext);

type WSMessage =
  | { type: "LTP"; instrument_key: string; ltp: number }
  | { type: "MARKET_UPDATE"; data: any }
  | { type: "ERROR"; msg: string }
  | { type: "TOKEN_EXPIRED"; msg: string; action_required?: string }
  | { type: "PNL"; net_pnl: number }
  | { type: "TRADE_UPDATE"; trade: Trade }
  | { type: "SESSION_EXPIRED" }
  | { type: "ENGINE_STATUS"; status: "RUNNING" | "PAUSED" };

export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const wsRef = useRef<ReconnectingWebSocket | null>(null);
  const { isAuthenticated, logout } = useAuthStore();
  const { updateLtp, setNetPnl, setEngineStatus } = useMarketStore();
  const { updateTrade } = useTradeStore();
  const [isConnected, setIsConnected] = React.useState(false);

  // ✅ FIX: Ref to track toast across re-renders/reconnects (moved to top level)
  const hasConnectedOnce = useRef(false);

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data: WSMessage = JSON.parse(event.data);
        logWebSocket.message(data.type, data);

        switch (data.type) {
          case "LTP":
            updateLtp(data.instrument_key, data.ltp);
            break;
          case "MARKET_UPDATE":
            // Delegate full market data update to store
            useMarketStore.getState().handleMarketUpdate(data.data);
            break;
          case "ERROR":
            useMarketStore.getState().handleBrokerError(data.msg);
            break;
          case "PNL":
            setNetPnl(data.net_pnl);
            logger.debug(COMPONENT_NAME, `P&L update received: ₹${data.net_pnl.toFixed(2)}`);
            break;
          case "TRADE_UPDATE":
            logger.info(COMPONENT_NAME, 'Trade update received', data.trade);
            updateTrade(data.trade);
            break;
          case "SESSION_EXPIRED":
            logger.warn(COMPONENT_NAME, 'Session expired message received');
            toast.error("Session expired due to inactivity");
            logout();
            break;
          case "TOKEN_EXPIRED":
            logger.warn(COMPONENT_NAME, 'Broker token expired message received');
            toast.error(data.msg || "Your Upstox session has expired", {
              description: "Please reconnect your broker account",
              duration: 10000,
              action: {
                label: 'Reconnect',
                onClick: () => {
                  window.location.href = '/account';
                }
              }
            });
            // Update broker connection status
            useMarketStore.getState().handleFeedDisconnected(); // ✅ FIX: Lint error
            break;
          case "ENGINE_STATUS":
            logger.info(COMPONENT_NAME, `Engine status update: ${data.status}`);
            setEngineStatus(data.status);
            if (data.status === "PAUSED") {
              toast.warning("Trading engine paused");
            }
            break;
        }
      } catch (error) {
        logger.error(COMPONENT_NAME, "Failed to parse WebSocket message", error);
      }
    },
    [updateLtp, setNetPnl, updateTrade, logout, setEngineStatus]
  );

  useEffect(() => {
    if (!isAuthenticated) {
      if (wsRef.current) {
        logger.info(COMPONENT_NAME, 'User not authenticated, closing WebSocket');
        wsRef.current.close();
        wsRef.current = null;
        setIsConnected(false);
      }
      return;
    }

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // ✅ FIX: Use Cookie for auth, no manual token param needed
    const wsUrl = `${wsProtocol}//${window.location.host}/ws/market-data`;

    logWebSocket.connect(wsUrl);

    wsRef.current = new ReconnectingWebSocket(wsUrl, [], {
      maxRetries: 10,
      connectionTimeout: 5000,
    });

    wsRef.current.onopen = () => {
      logWebSocket.connected();
      setIsConnected(true);

      // ✅ FIX: Only show toast once per session AND only on Trade page
      if (!hasConnectedOnce.current && window.location.pathname.includes('/trade')) {
        toast.success("Connected to market data", {
          action: {
            label: 'Close',
            onClick: () => console.log('Toast closed')
          },
          duration: 3000,
        });
        hasConnectedOnce.current = true;
      }
    };

    wsRef.current.onclose = () => {
      logWebSocket.disconnected();
      setIsConnected(false);
    };

    wsRef.current.onerror = (error) => {
      logWebSocket.error(error);
      setIsConnected(false);
    };

    wsRef.current.onmessage = handleMessage;

    const handleLogout = () => {
      logger.info(COMPONENT_NAME, 'Logout event received, closing WebSocket');
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };

    window.addEventListener("auth:logout", handleLogout);

    return () => {
      logger.debug(COMPONENT_NAME, 'Component unmounting, cleaning up WebSocket');
      window.removeEventListener("auth:logout", handleLogout);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [isAuthenticated, handleMessage]);

  return (
    <SocketContext.Provider value={{ isConnected }}>
      {children}
    </SocketContext.Provider>
  );
};
