import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useBrokerStore } from "@/stores/brokerStore";
import { toast } from "sonner";
import { Eye, EyeOff, Copy, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";

interface UpstoxSecretsModalProps {
    isOpen: boolean;
    onClose: () => void;
    initialStep?: "credentials" | "verification";
}

export const UpstoxSecretsModal: React.FC<UpstoxSecretsModalProps> = ({ isOpen, onClose, initialStep = "credentials" }) => {
    const navigate = useNavigate();
    const { saveSecrets, verifyConnection } = useBrokerStore();
    const [apiKey, setApiKey] = useState("");
    const [apiSecret, setApiSecret] = useState("");
    const [redirectUri, setRedirectUri] = useState(
        typeof window !== 'undefined' ? `${window.location.origin}/connect-broker` : ""
    );
    const [authCode, setAuthCode] = useState(""); // Can be code or token
    const [showSecret, setShowSecret] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [step, setStep] = useState<"credentials" | "verification">(initialStep);

    // Reset step when modal opens/closes or initialStep changes
    React.useEffect(() => {
        if (isOpen) {
            setStep(initialStep);
        }
    }, [isOpen, initialStep]);

    const handleSaveCredentials = async () => {
        if (!apiKey || !apiSecret || !redirectUri) {
            toast.error("Please fill in API Key, Secret, and Redirect URI");
            return;
        }

        setIsSubmitting(true);
        try {
            // Just save first
            await saveSecrets(apiKey, apiSecret, redirectUri);
            toast.success("Secrets saved. Now connect securely.");
            setStep("verification");
        } catch (error: any) {
            toast.error(`Failed to save secrets: ${error.response?.data?.detail || "Unknown error"}`);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleOpenLogin = async () => {
        try {
            const { data } = await api.get("/api/broker/upstox/auth-url");
            if (data.auth_url) {
                window.open(data.auth_url, "_blank");
                toast.info("Login page opened. Please authorize and copy the code from URL or wait for auto-redirect.", { duration: 6000 });
            }
        } catch (e) {
            toast.error("Failed to get auth URL. Ensure secrets are saved.");
        }
    };

    const handleVerifyCode = async () => {
        if (!authCode) { // Assuming authCode is the only input for now, as accessToken is not a state variable
            toast.error("Please enter the Auth Code or Access Token");
            return;
        }
        setIsSubmitting(true);
        try {
            await verifyConnection(authCode);

            toast.success("Broker connected successfully!", {
                description: "Redirecting to trading terminal..."
            });
            onClose();
            // Strict Redirect: Only after success
            navigate("/trade");
        } catch (error: any) {
            // Normalize backend error messages for toast
            const errorMessage = error.response?.data?.detail || "Verification failed. Please check your code/token.";
            toast.error("Connection Failed", {
                description: errorMessage
            });
            // Do NOT navigate. Do NOT close. Let user retry.
        } finally {
            setIsSubmitting(false);
        }
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        toast.success("Copied to clipboard");
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="sm:max-w-[425px] overflow-y-auto max-h-[90vh]">
                <DialogHeader>
                    <DialogTitle>Connect Upstox</DialogTitle>
                    <DialogDescription>
                        {step === "credentials"
                            ? "Step 1: Save your API Credentials."
                            : "Step 2: Authorize Upstox Connection."}
                    </DialogDescription>
                </DialogHeader>

                {step === "credentials" && (
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="apiKey">API Key (Client ID) *</Label>
                            <Input
                                id="apiKey"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                placeholder="Enter your API Key"
                                disabled={isSubmitting}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="apiSecret">API Secret *</Label>
                            <div className="relative">
                                <Input
                                    id="apiSecret"
                                    type={showSecret ? "text" : "password"}
                                    value={apiSecret}
                                    onChange={(e) => setApiSecret(e.target.value)}
                                    placeholder="Enter your API Secret"
                                    disabled={isSubmitting}
                                    className="pr-10"
                                />
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                                    onClick={() => setShowSecret(!showSecret)}
                                >
                                    {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </Button>
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="redirectUri">Redirect URI *</Label>
                            <div className="flex gap-2">
                                <Input
                                    id="redirectUri"
                                    value={redirectUri}
                                    onChange={(e) => setRedirectUri(e.target.value)}
                                    placeholder="e.g., http://localhost:8000/api/broker/upstox/callback"
                                    className="bg-background"
                                />
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="icon"
                                    onClick={() => copyToClipboard(redirectUri)}
                                >
                                    <Copy className="h-4 w-4" />
                                </Button>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Must match the Redirect URI in your Upstox Developer Console.
                            </p>
                        </div>
                        <DialogFooter>
                            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
                                Cancel
                            </Button>
                            <Button type="button" onClick={handleSaveCredentials} disabled={isSubmitting}>
                                {isSubmitting ? "Saving..." : "Save & Continue"}
                            </Button>
                        </DialogFooter>
                    </div>
                )}

                {step === "verification" && (
                    <div className="space-y-6 py-4">
                        <div className="bg-muted p-4 rounded-md space-y-3">
                            <p className="text-sm font-medium">1. Open Upstox Login</p>
                            <Button variant="default" size="sm" onClick={handleOpenLogin} className="w-full">
                                <ExternalLink className="mr-2 h-4 w-4" /> Open Login Page (New Tab)
                            </Button>
                            <p className="text-xs text-muted-foreground">
                                Login and copy the "code" from the address bar (e.g., `?code=m07ayw`) OR wait for auto-redirect.
                            </p>
                        </div>

                        <div className="space-y-2">
                            <p className="text-sm font-medium">2. Enter Auth Code (Manual)</p>
                            <Label htmlFor="authCode" className="sr-only">Auth Code</Label>
                            <Input
                                id="authCode"
                                value={authCode}
                                onChange={(e) => setAuthCode(e.target.value)}
                                placeholder="Paste Code (e.g. m07ayw) or Token"
                                disabled={isSubmitting}
                            />
                            <p className="text-xs text-muted-foreground">
                                If auto-redirect fails, paste the code here.
                            </p>
                        </div>

                        <DialogFooter className="flex justify-between sm:justify-between">
                            <Button type="button" variant="ghost" onClick={() => setStep("credentials")} disabled={isSubmitting}>
                                Back
                            </Button>
                            <div className="flex gap-2">
                                <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
                                    Close
                                </Button>
                                <Button type="button" onClick={handleVerifyCode} disabled={isSubmitting}>
                                    {isSubmitting ? "Verifying..." : "Verify & Connect"}
                                </Button>
                            </div>
                        </DialogFooter>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
};


