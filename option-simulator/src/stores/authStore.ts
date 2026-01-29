import { create } from "zustand";
import { api } from "@/lib/api";
import { logger, logAuth } from "@/lib/logger";

const STORE_NAME = "AuthStore";

export interface User {
  public_user_id: string;
  email: string;
  name: string;
  profile_pic?: string;
  virtual_balance?: number;
}

interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setAuthenticated: (value: boolean) => void;
  setLoading: (value: boolean) => void;
  checkAuth: () => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  // Start with isAuthenticated: false to prevent "flash of logged in state"
  // The auth check will verify using the cookie/session
  isAuthenticated: false,
  user: null,
  isLoading: true,  // Start with true to show loading state during initial auth check

  setUser: (user) => {
    if (user) {
      logger.info(STORE_NAME, `User set: ${user.email}`, { name: user.name });
    } else {
      logger.info(STORE_NAME, 'User cleared');
    }
    set({ user, isAuthenticated: !!user });
  },

  setAuthenticated: (value) => {
    logger.debug(STORE_NAME, `Auth status: ${value}`);
    set({ isAuthenticated: value });
  },

  setLoading: (value) => {
    logger.debug(STORE_NAME, `Loading: ${value}`);
    set({ isLoading: value });
  },

  checkAuth: async () => {
    logAuth.checkAuth();
    try {
      set({ isLoading: true });

      // Create timeout promise
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Auth check timeout')), 5000)
      );

      const { data } = await Promise.race([
        api.get("/api/auth/me"),
        timeoutPromise
      ]) as any;

      logAuth.authenticated(data.user);
      set({ user: data.user, isAuthenticated: true });
    } catch (error: any) {
      logAuth.unauthenticated();

      // Enhanced error logging
      const errorDetails: any = {
        message: error.message || 'Unknown error',
        hasResponse: !!error.response,
      };

      if (error.response) {
        errorDetails.status = error.response.status;
        errorDetails.statusText = error.response.statusText;
        errorDetails.data = error.response.data;
      }

      if (error.code) {
        errorDetails.code = error.code; // e.g., ECONNABORTED, ERR_NETWORK
      }

      logger.warn(STORE_NAME, `Auth check failed: ${errorDetails.message}`, errorDetails);

      // Clear auth state on any error that isn't a simple local issue
      // If server is down (no response) or 401/403, we should not show as authenticated
      if (!error.response || error.response.status === 401 || error.response.status === 403) {
        logger.warn(STORE_NAME, 'Clearing auth state due to failed check', {
          reason: !error.response ? 'No server response' : `HTTP ${error.response.status}`,
          detail: error.response?.data?.detail || 'Unknown'
        });
        set({ user: null, isAuthenticated: false });
      } else {
        // Other errors (e.g. 500) might be transient, but for safety in a simulator, 
        // it's better to require re-auth if we can't verify the session.
        logger.warn(STORE_NAME, 'Clearing auth state due to unexpected error', {
          status: error.response?.status,
          message: error.message
        });
        set({ user: null, isAuthenticated: false });
      }
    } finally {
      set({ isLoading: false });
    }
  },

  logout: async () => {
    logAuth.logout();

    // Optimistic logout: Clear state immediately
    set({ isAuthenticated: false, user: null, isLoading: false });
    window.dispatchEvent(new Event("auth:logout"));
    logger.info(STORE_NAME, 'Auth logout event dispatched (optimistic)');

    try {
      // Best-effort API call
      await api.post("/api/auth/logout");
      logger.info(STORE_NAME, 'Logout API call successful');
    } catch (error) {
      // Just log the error, the user is already logged out locally
      logger.error(STORE_NAME, 'Logout API call failed', error);
    }
  },
}));
