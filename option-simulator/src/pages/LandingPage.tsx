import React from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  TrendingUp,
  Target,
  BarChart3,
  Shield,
  Zap,
  Trophy,
  Chrome,
  ArrowRight,
  CheckCircle2,
  LineChart,
  Wallet,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Navbar } from "@/components/layout/Navbar";
import { useAuthStore } from "@/stores/authStore";

const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();

  const handleGoogleLogin = () => {
    // Temporary: Navigate directly to trade page (skip OAuth for now)
    navigate("/trade");
  };

  const handleGetStarted = () => {
    navigate("/trade");
  };

  const features = [
    {
      icon: <LineChart className="h-6 w-6" />,
      title: "Real-Time Market Data",
      description: "Live option chain with instant LTP updates via WebSocket connection.",
    },
    {
      icon: <Wallet className="h-6 w-6" />,
      title: "Virtual Money",
      description: "Practice with ₹10,00,000 virtual capital. No real money at risk.",
    },
    {
      icon: <BarChart3 className="h-6 w-6" />,
      title: "Track Performance",
      description: "Detailed analytics, win rate tracking, and P&L visualization.",
    },
    {
      icon: <Shield className="h-6 w-6" />,
      title: "Risk-Free Learning",
      description: "Learn options trading strategies without financial consequences.",
    },
    {
      icon: <Zap className="h-6 w-6" />,
      title: "Instant Execution",
      description: "Paper trades execute instantly with realistic slippage simulation.",
    },
    {
      icon: <Trophy className="h-6 w-6" />,
      title: "Gamified Experience",
      description: "Earn streaks, track achievements, and compete on leaderboards.",
    },
  ];

  const steps = [
    {
      step: "01",
      title: "Sign Up",
      description: "Quick Google sign-in to get started in seconds.",
    },
    {
      step: "02",
      title: "Connect Broker",
      description: "Link your Upstox account for live market data.",
    },
    {
      step: "03",
      title: "Start Trading",
      description: "Practice with virtual money on live option chains.",
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-16">
        {/* Background Effects */}
        <div className="absolute inset-0 bg-grid-pattern bg-grid opacity-20" />
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -left-40 -top-40 h-[500px] w-[500px] rounded-full bg-primary/20 blur-[120px]" />
          <div className="absolute -bottom-40 -right-40 h-[500px] w-[500px] rounded-full bg-accent/20 blur-[120px]" />
        </div>

        <div className="relative mx-auto max-w-7xl px-4 py-24 sm:px-6 sm:py-32 lg:px-8">
          <div className="text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <span className="inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary">
                <Zap className="h-4 w-4" />
                Paper Trading Simulator
              </span>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="mt-8 text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl"
            >
              Master Options Trading
              <br />
              <span className="bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                Without the Risk
              </span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground"
            >
              Practice F&O trading with real-time market data and virtual money. 
              Build your skills, test strategies, and track your performance — all risk-free.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
              className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
            >
              <Button
                onClick={handleGetStarted}
                size="lg"
                className="btn-glow-primary gap-2 bg-primary px-8 py-6 text-lg font-semibold text-primary-foreground hover:bg-primary/90"
              >
                {isAuthenticated ? "Go to Dashboard" : "Get Started Free"}
                <ArrowRight className="h-5 w-5" />
              </Button>
              <Button
                variant="outline"
                size="lg"
                onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}
                className="gap-2 px-8 py-6 text-lg"
              >
                Learn More
              </Button>
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.4 }}
              className="mt-6 text-sm text-muted-foreground"
            >
              <CheckCircle2 className="mr-1 inline h-4 w-4 text-profit" />
              No credit card required • Free forever • Real market data
            </motion.p>
          </div>

          {/* Hero Image/Preview */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.5 }}
            className="mt-16"
          >
            <div className="relative mx-auto max-w-5xl overflow-hidden rounded-2xl border border-border/50 bg-card/50 p-2 shadow-2xl backdrop-blur-sm">
              <div className="rounded-xl bg-background p-4">
                {/* Mock Dashboard Preview */}
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="rounded-lg bg-secondary/50 p-4">
                    <p className="text-sm text-muted-foreground">Net P&L</p>
                    <p className="mt-2 text-2xl font-bold text-profit">+₹24,500</p>
                  </div>
                  <div className="rounded-lg bg-secondary/50 p-4">
                    <p className="text-sm text-muted-foreground">Win Rate</p>
                    <p className="mt-2 text-2xl font-bold text-foreground">68%</p>
                  </div>
                  <div className="rounded-lg bg-secondary/50 p-4">
                    <p className="text-sm text-muted-foreground">Streak</p>
                    <p className="mt-2 text-2xl font-bold text-streak">🔥 5</p>
                  </div>
                </div>
                <div className="mt-4 rounded-lg border border-border/50 bg-secondary/30 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">NIFTY 24500 CE</span>
                    <span className="text-sm font-mono text-profit">₹245.50 ↑</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">NIFTY 24400 PE</span>
                    <span className="text-sm font-mono text-loss">₹180.25 ↓</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="relative py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Everything You Need to Learn
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              A complete paper trading platform designed for aspiring options traders.
            </p>
          </motion.div>

          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="trade-card p-6"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  {feature.icon}
                </div>
                <h3 className="text-lg font-semibold text-foreground">{feature.title}</h3>
                <p className="mt-2 text-muted-foreground">{feature.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="relative bg-secondary/20 py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              How It Works
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              Get started in minutes with our simple onboarding process.
            </p>
          </motion.div>

          <div className="mt-16 grid gap-8 lg:grid-cols-3">
            {steps.map((step, index) => (
              <motion.div
                key={step.step}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.15 }}
                className="relative text-center"
              >
                <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
                  <span className="text-2xl font-bold text-primary">{step.step}</span>
                </div>
                <h3 className="text-xl font-semibold text-foreground">{step.title}</h3>
                <p className="mt-2 text-muted-foreground">{step.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="relative py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Simple, Free Pricing
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              Start learning options trading today. No hidden fees.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="mx-auto mt-16 max-w-md"
          >
            <div className="trade-card overflow-hidden">
              <div className="bg-gradient-to-r from-primary/10 to-accent/10 p-6 text-center">
                <h3 className="text-2xl font-bold text-foreground">Free Forever</h3>
                <p className="mt-2 text-4xl font-bold text-foreground">
                  ₹0<span className="text-lg font-normal text-muted-foreground">/month</span>
                </p>
              </div>
              <div className="p-6">
                <ul className="space-y-4">
                  {[
                    "Real-time market data",
                    "₹10,00,000 virtual capital",
                    "Unlimited paper trades",
                    "Performance analytics",
                    "Trade history & reports",
                    "Greeks display",
                    "Risk calculator",
                  ].map((feature) => (
                    <li key={feature} className="flex items-center gap-3">
                      <CheckCircle2 className="h-5 w-5 text-profit" />
                      <span className="text-foreground">{feature}</span>
                    </li>
                  ))}
                </ul>
                <Button
                  onClick={handleGetStarted}
                  className="btn-glow-primary mt-8 w-full gap-2 bg-primary py-6 text-lg font-semibold text-primary-foreground hover:bg-primary/90"
                >
                  <Chrome className="h-5 w-5" />
                  {isAuthenticated ? "Go to Dashboard" : "Get Started"}
                </Button>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative overflow-hidden py-24">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute left-1/2 top-0 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-primary/10 blur-[120px]" />
        </div>

        <div className="relative mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl font-bold text-foreground sm:text-4xl">
              Ready to Start Trading?
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              Join thousands of traders who are learning and improving their skills 
              with our paper trading simulator.
            </p>
            <Button
              onClick={handleGetStarted}
              size="lg"
              className="btn-glow-primary mt-8 gap-2 bg-primary px-10 py-6 text-lg font-semibold text-primary-foreground hover:bg-primary/90"
            >
              {isAuthenticated ? "Go to Dashboard" : "Start Free Today"}
              <ArrowRight className="h-5 w-5" />
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/50 bg-background py-12">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                <TrendingUp className="h-4 w-4 text-primary" />
              </div>
              <span className="font-bold text-foreground">OptionSim</span>
            </div>
            <div className="flex gap-6 text-sm text-muted-foreground">
              <a href="/privacy-policy" className="hover:text-foreground">Privacy Policy</a>
              <a href="/terms" className="hover:text-foreground">Terms of Service</a>
              <a href="/disclaimer" className="hover:text-foreground">Disclaimer</a>
            </div>
            <p className="text-sm text-muted-foreground">
              © 2024 OptionSim. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
