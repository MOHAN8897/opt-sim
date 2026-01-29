import React from "react";
import { motion } from "framer-motion";
import { TrendingUp, Chrome, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

const LoginPage: React.FC = () => {
  const handleGoogleLogin = () => {
    console.log("Login button clicked. Redirecting to /api/auth/login...");
    // Redirect to backend OAuth endpoint
    window.location.href = "/api/auth/login";
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background">
      {/* Animated background grid */}
      <div className="absolute inset-0 bg-grid-pattern bg-grid opacity-20" />

      {/* Gradient orbs */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-40 -top-40 h-80 w-80 rounded-full bg-primary/20 blur-[100px]" />
        <div className="absolute -bottom-40 -right-40 h-80 w-80 rounded-full bg-accent/20 blur-[100px]" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative z-10 w-full max-w-md px-4 sm:px-6"
      >
        <Button
          variant="ghost"
          onClick={() => (window.location.href = "/")}
          className="mb-4 -ml-2 text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Home
        </Button>

        <div className="trade-card p-6 sm:p-8">
          {/* Logo */}
          <motion.div
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring" }}
            className="mb-8 flex flex-col items-center"
          >
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
              <TrendingUp className="h-10 w-10 text-primary" />
            </div>
            <h1 className="text-2xl font-bold text-foreground">OptionSim</h1>
            <p className="mt-2 text-center text-sm text-muted-foreground">
              Paper trade options with real-time data. No risk, all the learning.
            </p>
          </motion.div>

          {/* Features */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mb-8 space-y-3"
          >
            {[
              "Real-time market data",
              "Practice with virtual money",
              "Track your performance",
              "Learn without the risk",
            ].map((feature, index) => (
              <div
                key={feature}
                className="flex items-center gap-3 text-sm text-muted-foreground"
              >
                <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20">
                  <div className="h-2 w-2 rounded-full bg-primary" />
                </div>
                {feature}
              </div>
            ))}
          </motion.div>

          {/* Login Button */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
          >
            <Button
              onClick={handleGoogleLogin}
              className="btn-glow-primary w-full gap-3 bg-primary py-6 text-base font-semibold text-primary-foreground hover:bg-primary/90"
            >
              <Chrome className="h-5 w-5" />
              Continue with Google
            </Button>
          </motion.div>

          {/* Disclaimer */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            className="mt-6 text-center text-xs text-muted-foreground"
          >
            By continuing, you agree to our{" "}
            <a href="/terms" className="text-primary hover:underline">
              Terms of Service
            </a>{" "}
            and{" "}
            <a href="/privacy-policy" className="text-primary hover:underline">
              Privacy Policy
            </a>
          </motion.p>
        </div>

        {/* Demo mode notice */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1 }}
          className="mt-6 text-center"
        >
          <p className="text-xs text-muted-foreground">
            This is a paper trading simulator.{" "}
            <span className="text-profit">No real money involved.</span>
          </p>
        </motion.div>
      </motion.div>
    </div>
  );
};

export default LoginPage;
