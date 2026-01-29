import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { useBrokerStore } from "@/stores/brokerStore";
import { Loader2 } from "lucide-react";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuthStore();
  const { status, checkConnection } = useBrokerStore();
  const location = useLocation();

  // On mount or auth change, check broker connection
  React.useEffect(() => {
    if (isAuthenticated) {
      checkConnection();
    }
  }, [isAuthenticated, checkConnection]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-10 w-10 animate-spin text-primary" />
          <p className="text-muted-foreground">Restoring session...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Redirect logic removed to prevent race conditions on refresh. 
  // TradePage handles its own "Locked" state presentation.
  // if (location.pathname === "/trade" && status !== "TOKEN_VALID") {
  //   return <Navigate to="/account" replace />;
  // }

  // If user is connected and accessing account, allow access (user might want to disconnect)
  // Logic: Only block /trade if not connected. All other protected routes are accessible if authenticated.

  return <>{children}</>;
};
