import { create } from "zustand";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

const STORE_NAME = "BrokerStore";

import { BrokerStatus } from "@/types/trading";

export type { BrokerStatus }; // Re-export for convenience or just use enum

interface BrokerState {
  status: BrokerStatus;
  tokenExpiry: string | null;
  isLoading: boolean;
  setStatus: (status: BrokerStatus) => void;
  setTokenExpiry: (expiry: string | null) => void;
  checkConnection: () => Promise<void>;
  verifyConnection: (codeOrToken: string) => Promise<void>;
  saveSecrets: (apiKey: string, apiSecret: string, redirectUri: string, accessToken?: string) => Promise<void>;
  disconnect: () => Promise<void>;
  reset: () => void;
}

export const useBrokerStore = create<BrokerState>((set, get) => ({
  status: BrokerStatus.NO_SECRETS,
  tokenExpiry: null,
  isLoading: false,

  setStatus: (status) => {
    logger.info(STORE_NAME, `Broker status changed: ${status}`);
    set({ status });
  },

  setTokenExpiry: (expiry) => {
    logger.debug(STORE_NAME, `Token expiry set: ${expiry || 'null'}`);
    set({ tokenExpiry: expiry });
  },

  checkConnection: async () => {
    logger.info(STORE_NAME, 'Checking broker connection status...');
    set({ isLoading: true });
    try {
      const response = await api.get("/api/broker/status");
      logger.info(STORE_NAME, `Broker connection check successful`, {
        status: response.data.status,
        tokenExpiry: response.data.token_expiry
      });

      set({
        status: response.data.status,
        tokenExpiry: response.data.token_expiry,
        isLoading: false
      });
    } catch (error) {
      logger.error(STORE_NAME, 'Broker connection check failed', error);
      // Do NOT set NO_SECRETS on generic error (e.g. 500 or Network Error)
      // Only set if backend returns 401 or specific status
      // set({ status: "NO_SECRETS", tokenExpiry: null, isLoading: false });
      set({ isLoading: false });
    }
  },

  verifyConnection: async (codeOrToken: string) => {
    logger.info(STORE_NAME, 'Verifying connection manually');
    set({ isLoading: true });
    try {
      const payload: any = {};
      // Simple heuristic: Code usually short (< 10 chars for Upstox?), Token very long (JWT or UUID-like)
      // Upstox codes are usually 6 chars? Let's send as 'code' mostly, backend handles "long code = token" logic.
      payload.code = codeOrToken;

      const { data } = await api.post("/api/broker/upstox/verify-connection", payload);

      if (data.status) {
        set({ status: data.status, isLoading: false });
      }

      logger.info(STORE_NAME, 'Verification successful');
    } catch (error) {
      logger.error(STORE_NAME, 'Verification failed', error);
      set({ isLoading: false });
      throw error;
    }
  },

  saveSecrets: async (apiKey: string, apiSecret: string, redirectUri: string, accessToken?: string) => {
    logger.info(STORE_NAME, 'Saving broker secrets');
    set({ isLoading: true });
    try {
      const payload: any = {
        api_key: apiKey,
        api_secret: apiSecret,
        redirect_uri: redirectUri
      };
      if (accessToken) {
        payload.access_token = accessToken;
      }

      const { data } = await api.post("/api/broker/upstox/save-secrets", payload);

      // Update status based on backend response
      if (data.broker_status) {
        set({ status: data.broker_status, isLoading: false });
      } else {
        // Fallback: Re-verify status from backend instead of guessing
        await get().checkConnection();
      }

      logger.info(STORE_NAME, 'Secrets saved successfully');
    } catch (error) {
      logger.error(STORE_NAME, 'Failed to save secrets', error);
      set({ isLoading: false });
      throw error;
    }
  },

  disconnect: async () => {
    logger.info(STORE_NAME, 'Disconnecting broker');
    set({ isLoading: true });
    try {
      await api.post("/api/broker/upstox/disconnect");
      set({ status: BrokerStatus.NO_SECRETS, tokenExpiry: null, isLoading: false });
      logger.info(STORE_NAME, 'Broker disconnected');
    } catch (error) {
      logger.error(STORE_NAME, 'Failed to disconnect', error);
      set({ isLoading: false });
      throw error;
    }
  },

  reset: () => {
    logger.info(STORE_NAME, 'Resetting broker connection state');
    set({ status: BrokerStatus.NO_SECRETS, tokenExpiry: null, isLoading: false });
  },
}));
