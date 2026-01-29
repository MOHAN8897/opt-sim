import { useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useAuthStore } from "@/stores/authStore";
import { logger } from "@/lib/logger";

const INACTIVITY_TIMEOUT = 20 * 60 * 1000; // 20 minutes in milliseconds
const CHECK_INTERVAL = 30 * 1000; // Check every 30 seconds

export const useInactivityLogout = () => {
    const { logout } = useAuth();
    const { isAuthenticated } = useAuthStore();
    const lastActivityRef = useRef<number>(Date.now());
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    const resetTimer = useCallback(() => {
        lastActivityRef.current = Date.now();
    }, []);

    const checkInactivity = useCallback(() => {
        if (!isAuthenticated) return;

        const now = Date.now();
        const inactiveDuration = now - lastActivityRef.current;

        if (inactiveDuration >= INACTIVITY_TIMEOUT) {
            logger.info("InactivityLogout", "User inactive for 20 minutes, logging out");
            logout();
        }
    }, [isAuthenticated, logout]);

    useEffect(() => {
        if (!isAuthenticated) {
            if (timerRef.current) {
                clearInterval(timerRef.current);
                timerRef.current = null;
            }
            return;
        }

        // Set up activity listeners
        const activityEvents = [
            "mousedown",
            "mousemove",
            "keydown",
            "scroll",
            "touchstart",
            "click",
        ];

        activityEvents.forEach((event) => {
            window.addEventListener(event, resetTimer);
        });

        // Set up inactivity check interval
        timerRef.current = setInterval(checkInactivity, CHECK_INTERVAL);

        return () => {
            activityEvents.forEach((event) => {
                window.removeEventListener(event, resetTimer);
            });
            if (timerRef.current) {
                clearInterval(timerRef.current);
            }
        };
    }, [isAuthenticated, resetTimer, checkInactivity]);
};
