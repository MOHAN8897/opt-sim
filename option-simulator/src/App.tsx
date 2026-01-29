import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/providers/AuthProvider";
import { SocketProvider } from "@/providers/SocketProvider";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import AuthCallbackPage from "./pages/AuthCallbackPage";
import Index from "./pages/Index";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import TradePage from "./pages/TradePage";
import PortfolioPage from "./pages/PortfolioPage";
import AccountPage from "./pages/AccountPage";
import PrivacyPolicyPage from "./pages/PrivacyPolicyPage";
import TermsPage from "./pages/TermsPage";
import DisclaimerPage from "./pages/DisclaimerPage";
import NotFound from "./pages/NotFound";
import { useEffect } from "react";
import { useInactivityLogout } from "@/hooks/useInactivityLogout";
import { useBrokerStore } from "@/stores/brokerStore";
import { useUIStore } from "@/stores/uiStore";
import { useMarketStore } from "@/stores/marketStore";
import { toast } from "sonner";

const queryClient = new QueryClient();

const TokenMonitor = () => {
  const { tokenExpiry, status } = useBrokerStore();
  useEffect(() => {
    if (status === "TOKEN_VALID" && tokenExpiry) {
      const expiryDate = new Date(tokenExpiry);
      const now = new Date();

      // Compare timestamps to handle timezone correctly
      // Backend sends UTC, but Date constructor handles it properly
      if (now.getTime() > expiryDate.getTime()) {
        toast.error("Upstox Session Expired", {
          description: "Please reconnect your broker to continue trading.",
          duration: Infinity, // Persistent until dismissed or reconnected
          action: {
            label: "Reconnect",
            onClick: () => window.location.href = "/account"
          }
        });
      }
    }
  }, [tokenExpiry, status]);
  return null;
};

const SessionMonitor = () => {
  useInactivityLogout();
  return null;
};

// 🔴 FIX #4: Initialize stores from localStorage on app start
const StoreInitializer = () => {
  useEffect(() => {
    // Restore UI state (selectedOption, etc.)
    useUIStore.getState().initializeFromLocalStorage();
  }, []);
  return null;
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <BrowserRouter>
        <AuthProvider>
          <SocketProvider>
            <Toaster />
            <Sonner position="top-right" closeButton richColors />
            <TokenMonitor />
            <SessionMonitor />
            <StoreInitializer />
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/auth/callback" element={<AuthCallbackPage />} />
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute>
                    <DashboardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/trade"
                element={
                  <ProtectedRoute>
                    <TradePage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/portfolio"
                element={
                  <ProtectedRoute>
                    <PortfolioPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/account"
                element={
                  <ProtectedRoute>
                    <AccountPage />
                  </ProtectedRoute>
                }
              />
              <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
              <Route path="/terms" element={<TermsPage />} />
              <Route path="/disclaimer" element={<DisclaimerPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </SocketProvider>
        </AuthProvider>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
