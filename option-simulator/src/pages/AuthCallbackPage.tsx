import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import { useBrokerStore } from "@/stores/brokerStore";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";
import { logger } from "@/lib/logger";

const COMPONENT_NAME = "AuthCallbackPage";

export default function AuthCallbackPage() {
    const navigate = useNavigate();
    const { setUser, setLoading } = useAuthStore();
    const { checkConnection } = useBrokerStore();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const handleAuthCallback = async () => {
            logger.info(COMPONENT_NAME, "OAuth callback received, verifying authentication");
            setLoading(true);

            try {
                // Wait a moment for cookie to be set by backend redirect
                await new Promise(resolve => setTimeout(resolve, 500));

                // Check authentication status
                logger.info(COMPONENT_NAME, "Checking authentication status");
                const response = await api.get("/api/auth/me");

                if (response.data.user) {
                    logger.info(COMPONENT_NAME, "User authenticated successfully", {
                        email: response.data.user.email
                    });
                    setUser(response.data.user);

                    // Check broker connection status
                    logger.info(COMPONENT_NAME, "Checking broker connection");
                    await checkConnection();

                    // Get broker status from store after check completes
                    const brokerStatus = useBrokerStore.getState().status;

                    // Redirect based on broker status
                    if (brokerStatus === "TOKEN_VALID") {
                        logger.info(COMPONENT_NAME, "Broker connected, redirecting to trade page");
                        navigate("/trade", { replace: true });
                    } else {
                        logger.info(COMPONENT_NAME, "Broker not connected, redirecting to account page");
                        navigate("/account", { replace: true });
                    }
                } else {
                    throw new Error("No user data received");
                }
            } catch (err) {
                logger.error(COMPONENT_NAME, "Authentication verification failed", err);
                setError("Authentication failed. Please try logging in again.");
                setUser(null);

                // Redirect to login after showing error briefly
                setTimeout(() => {
                    navigate("/login", { replace: true });
                }, 2000);
            } finally {
                setLoading(false);
            }
        };

        handleAuthCallback();
    }, [navigate, setUser, setLoading, checkConnection]);

    if (error) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-background">
                <div className="flex flex-col items-center gap-4 text-center">
                    <div className="rounded-full bg-destructive/10 p-3">
                        <svg
                            className="h-6 w-6 text-destructive"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                        >
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                            />
                        </svg>
                    </div>
                    <p className="text-lg font-medium text-destructive">{error}</p>
                    <p className="text-sm text-muted-foreground">Redirecting to login...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex min-h-screen items-center justify-center bg-background">
            <div className="flex flex-col items-center gap-4">
                <Loader2 className="h-10 w-10 animate-spin text-primary" />
                <p className="text-lg font-medium">Completing authentication...</p>
                <p className="text-sm text-muted-foreground">Please wait while we set up your session</p>
            </div>
        </div>
    );
}
