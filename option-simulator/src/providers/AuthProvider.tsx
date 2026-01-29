import React, { useCallback, useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useBrokerStore } from "@/stores/brokerStore";
import { useMarketStore } from "@/stores/marketStore";
import { useTradeStore } from "@/stores/tradeStore";
import { logger } from "@/lib/logger";
import { AuthContext } from "@/contexts/AuthContext";

const COMPONENT_NAME = "AuthProvider";

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { checkAuth: storeCheckAuth, logout: storeLogout } = useAuthStore();
  const { reset: resetBroker } = useBrokerStore();
  const { reset: resetMarket } = useMarketStore();
  const { reset: resetTrades } = useTradeStore();

  const checkAuth = useCallback(async () => {
    logger.info(COMPONENT_NAME, 'Initiating auth check via store');
    await storeCheckAuth();
  }, [storeCheckAuth]);

  const logout = useCallback(async () => {
    logger.info(COMPONENT_NAME, 'Logout initiated');
    try {
      // Clean up other stores first
      resetBroker();
      resetMarket();
      resetTrades();
      // Then perform auth logout (which calls API and clears auth store)
      await storeLogout();

      window.dispatchEvent(new CustomEvent("auth:logout"));
      logger.info(COMPONENT_NAME, 'Logout complete');
    } catch (error) {
      logger.error(COMPONENT_NAME, 'Logout failed', error);
    }
  }, [storeLogout, resetBroker, resetMarket, resetTrades]);

  useEffect(() => {
    logger.info(COMPONENT_NAME, 'Component mounted, checking auth');
    checkAuth();

    const handleUnauthorized = () => {
      logger.warn(COMPONENT_NAME, 'Unauthorized event received - clearing auth state');
      storeLogout();
      resetBroker();
      resetMarket();
      resetTrades();
    };

    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => {
      logger.debug(COMPONENT_NAME, 'Component unmounting');
      window.removeEventListener("auth:unauthorized", handleUnauthorized);
    };
  }, [checkAuth, storeLogout, resetBroker, resetMarket, resetTrades]);

  return (
    <AuthContext.Provider value={{ checkAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
