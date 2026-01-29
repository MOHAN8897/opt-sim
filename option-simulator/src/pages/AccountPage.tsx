import React, { useState } from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { User as UserIcon, Shield, Bell, CreditCard, Link2, LogOut, Copy, ExternalLink } from "lucide-react";
import { MainLayout } from "@/components/layout/MainLayout";
import { useAuthStore } from "@/stores/authStore";
import { useBrokerStore, BrokerStatus } from "@/stores/brokerStore";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { UpstoxSecretsModal } from "@/components/account/UpstoxSecretsModal";
import { api } from "@/lib/api";

const AccountPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { status: brokerStatus, tokenExpiry, disconnect, checkConnection, isLoading } = useBrokerStore();
  const { logout } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isSecretsModalOpen, setIsSecretsModalOpen] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    const toastId = toast.loading("Logging out...");
    try {
      await logout();
      toast.success("Logged out successfully", { id: toastId });
      navigate("/");
    } catch (error) {
      toast.error("Failed to logout", { id: toastId });
      setIsLoggingOut(false);
    }
  };

  const handleConnectBroker = () => {
    // Always open modal. The modal handles the "Step 2" verification flow 
    // including opening Upstox in a new tab and accepting the manual code.
    setIsSecretsModalOpen(true);
  };

  const handleDisconnect = async () => {
    if (confirm("Are you sure you want to disconnect? This will clear your stored secrets.")) {
      try {
        await disconnect();
        toast.success("Broker disconnected");
      } catch (e) {
        toast.error("Failed to disconnect");
      }
    }
  }

  const copyUserId = () => {
    if (user?.public_user_id) {
      navigator.clipboard.writeText(user.public_user_id);
      toast.success("User ID copied to clipboard");
    }
  };

  return (
    <MainLayout>
      <div className="space-y-4 md:space-y-6">
        <UpstoxSecretsModal
          isOpen={isSecretsModalOpen}
          initialStep={brokerStatus === "SECRETS_SAVED" || brokerStatus === "TOKEN_EXPIRED" ? "verification" : "credentials"}
          onClose={() => {
            setIsSecretsModalOpen(false);
          }}
        />

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-xl md:text-2xl font-bold text-foreground">Account</h1>
          <p className="mt-1 text-sm md:text-base text-muted-foreground">
            Manage your profile and connections
          </p>
        </motion.div>

        <div className="grid gap-4 md:gap-6 lg:grid-cols-2">
          {/* Profile Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="trade-card p-4 md:p-6"
          >
            <div className="mb-4 md:mb-6 flex items-center gap-3 md:gap-4">
              {user?.profile_pic ? (
                <img src={user.profile_pic} alt="Profile" className="h-12 w-12 md:h-16 md:w-16 rounded-full border-2 border-primary/20" />
              ) : (
                <div className="flex h-12 w-12 md:h-16 md:w-16 items-center justify-center rounded-full bg-primary/20 text-lg md:text-2xl font-bold text-primary">
                  {user?.name?.charAt(0) || user?.email?.charAt(0) || "U"}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <h2 className="text-lg md:text-xl font-semibold text-foreground truncate">{user?.name || "User"}</h2>
                <p className="text-sm md:text-base text-muted-foreground truncate">{user?.email}</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center gap-3 rounded-lg bg-secondary/50 p-3">
                <UserIcon className="h-5 w-5 text-muted-foreground" />
                <div className="flex-1 overflow-hidden">
                  <p className="text-sm text-muted-foreground">User ID</p>
                  <div className="flex items-center gap-2">
                    <p className="font-mono text-sm text-foreground truncate">{user?.public_user_id || "—"}</p>
                    {user?.public_user_id && (
                      <Button variant="ghost" size="icon" className="h-6 w-6" onClick={copyUserId}>
                        <Copy className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3 rounded-lg bg-secondary/50 p-3">
                <Shield className="h-5 w-5 text-muted-foreground" />
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">Account Type</p>
                  <p className="font-medium text-foreground">Paper Trading</p>
                </div>
                <span className="rounded-full bg-profit/20 px-2 py-0.5 text-xs font-semibold text-profit">
                  Active
                </span>
              </div>
            </div>
          </motion.div>

          {/* Broker Connection */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="trade-card p-4 md:p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-foreground">Broker Connection</h3>
              {/* Manual refresh removed in favor of auto-refresh prompts */}
            </div>

            <div
              className={cn(
                "rounded-lg border p-4",
                brokerStatus === "TOKEN_VALID"
                  ? "border-profit/30 bg-profit/5"
                  : brokerStatus === "TOKEN_EXPIRED"
                    ? "border-streak/30 bg-streak/5"
                    : "border-border bg-secondary/30"
              )}
            >
              <div className="flex items-center gap-3">
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-lg",
                    brokerStatus === "TOKEN_VALID"
                      ? "bg-profit/20"
                      : brokerStatus === "TOKEN_EXPIRED"
                        ? "bg-streak/20"
                        : "bg-muted"
                  )}
                >
                  <Link2
                    className={cn(
                      "h-5 w-5",
                      brokerStatus === "TOKEN_VALID"
                        ? "text-profit"
                        : brokerStatus === "TOKEN_EXPIRED"
                          ? "text-streak"
                          : "text-muted-foreground"
                    )}
                  />
                </div>
                <div className="flex-1">
                  <p className="font-medium text-foreground">
                    {brokerStatus === "TOKEN_VALID"
                      ? "Upstox Connected"
                      : brokerStatus === "TOKEN_EXPIRED"
                        ? "Token Expired"
                        : brokerStatus === "SECRETS_SAVED"
                          ? "Secrets Saved"
                          : "Not Connected"}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {brokerStatus === "TOKEN_VALID" && tokenExpiry
                      ? `Expires: ${new Date(tokenExpiry).toLocaleString()}`
                      : brokerStatus === "TOKEN_EXPIRED"
                        ? "Please reconnect to continue"
                        : brokerStatus === "SECRETS_SAVED"
                          ? "Complete authorization to trade"
                          : "Connect Upstox to receive live data"}
                  </p>
                </div>
              </div>

              {brokerStatus !== "TOKEN_VALID" ? (
                <div className="flex flex-col gap-2 mt-4">
                  <Button
                    onClick={handleConnectBroker}
                    className="w-full"
                    variant={brokerStatus === "TOKEN_EXPIRED" ? "destructive" : "default"}
                    disabled={isLoading}
                  >
                    {brokerStatus === "SECRETS_SAVED" ? (
                      "Complete Setup / Enter Code"
                    ) : (
                      "Connect Broker"
                    )}
                  </Button>

                  {(brokerStatus === "SECRETS_SAVED" || brokerStatus === "TOKEN_EXPIRED") && (
                    <Button
                      variant="outline"
                      onClick={() => setIsSecretsModalOpen(true)}
                      disabled={isLoading}
                      className="w-full"
                    >
                      Edit Secrets
                    </Button>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-2 mt-4">
                  {/* Allow editing even when connected if needed, or just disconnect first */}
                  {/* User asked for edit button, let's keep it simple: Disconnect to edit usually better ?? */}
                  {/* "11️⃣ Editing Secrets (Existing User) Allowed when status is: SECRETS_SAVED TOKEN_VALID TOKEN_EXPIRED" */}
                  <Button
                    onClick={() => setIsSecretsModalOpen(true)}
                    className="w-full"
                    variant="outline"
                  >
                    Edit Secrets
                  </Button>
                  <Button
                    onClick={handleDisconnect}
                    className="w-full"
                    variant="destructive"
                  >
                    Disconnect
                  </Button>
                </div>
              )}
            </div>

            <p className="mt-4 text-xs text-muted-foreground">
              * Support for Upstox API. API Keys are encrypted and stored securely.
            </p>
          </motion.div>

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="trade-card p-4 md:p-6 lg:col-span-2"
          >
            <h3 className="mb-4 text-lg font-semibold text-foreground">Quick Actions</h3>
            <div className="space-y-2">
              <Button
                variant="outline"
                className="w-full justify-start gap-3 hover:bg-accent cursor-pointer"
                disabled={false}
              >
                <Bell className="h-5 w-5" />
                Notification Settings
              </Button>
              <Button
                variant="outline"
                className="w-full justify-start gap-3 hover:bg-accent cursor-pointer"
                disabled={false}
              >
                <CreditCard className="h-5 w-5" />
                Virtual Balance
              </Button>
              <Button
                variant="outline"
                className="w-full justify-start gap-3 text-destructive border-destructive/50 hover:bg-destructive/10 hover:text-destructive cursor-pointer"
                onClick={handleLogout}
                disabled={isLoggingOut}
              >
                <LogOut className="h-5 w-5" />
                {isLoggingOut ? "Logging out..." : "Logout"}
              </Button>
            </div>
          </motion.div>

        </div>
      </div>
    </MainLayout>
  );
};

export default AccountPage;
