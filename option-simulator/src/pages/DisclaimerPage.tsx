import React from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowLeft, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

const DisclaimerPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border">
        <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
          <Link to="/">
            <Button variant="ghost" size="sm" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Back to Home
            </Button>
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-4xl px-4 py-12 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="mb-8 flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-streak/10">
              <AlertTriangle className="h-7 w-7 text-streak" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">Disclaimer</h1>
              <p className="text-muted-foreground">Important Information for Users</p>
            </div>
          </div>

          <div className="prose prose-invert max-w-none space-y-8">
            {/* Important Notice */}
            <section className="rounded-lg border-2 border-streak/30 bg-streak/10 p-6">
              <h2 className="mb-4 flex items-center gap-2 text-xl font-semibold text-streak">
                <AlertTriangle className="h-5 w-5" />
                Important Notice
              </h2>
              <p className="text-foreground leading-relaxed">
                OptionSim is a <strong>paper trading simulator</strong> designed exclusively for 
                educational and practice purposes. This platform does NOT involve any real money, 
                actual securities transactions, or investment of any kind.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">No Investment Advice</h2>
              <p className="text-muted-foreground leading-relaxed">
                Nothing on this Platform constitutes financial advice, investment advice, trading advice, 
                or any other sort of advice. The content provided is for informational and educational 
                purposes only. You should not construe any such information as legal, tax, investment, 
                financial, or other advice.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">Virtual Trading Environment</h2>
              <div className="space-y-4 text-muted-foreground">
                <p className="leading-relaxed">Users must understand that:</p>
                <ul className="list-disc space-y-2 pl-6">
                  <li>
                    <strong className="text-foreground">Virtual Currency Only:</strong> All trading on 
                    this platform uses virtual (fake) money. No real currency is exchanged.
                  </li>
                  <li>
                    <strong className="text-foreground">Simulated Market Data:</strong> Market data 
                    displayed may be simulated, delayed, or may not accurately reflect actual market 
                    conditions.
                  </li>
                  <li>
                    <strong className="text-foreground">No Real Profits/Losses:</strong> Any profits 
                    or losses shown are entirely virtual and have no real-world monetary value.
                  </li>
                  <li>
                    <strong className="text-foreground">Execution Differences:</strong> Paper trade 
                    execution may differ significantly from real market execution in terms of fills, 
                    slippage, and timing.
                  </li>
                </ul>
              </div>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">Risk Warning</h2>
              <div className="space-y-4 text-muted-foreground">
                <p className="leading-relaxed">
                  Options trading involves significant risk and is not suitable for all investors. 
                  Before engaging in real options trading, you should:
                </p>
                <ul className="list-disc space-y-2 pl-6">
                  <li>Understand that you can lose more than your initial investment</li>
                  <li>Consult with a qualified financial advisor</li>
                  <li>Thoroughly research and understand options strategies</li>
                  <li>Only trade with money you can afford to lose</li>
                  <li>Be aware of the time decay (theta) effect on options</li>
                  <li>Understand the impact of volatility on option prices</li>
                </ul>
              </div>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">Paper Trading Limitations</h2>
              <div className="space-y-4 text-muted-foreground">
                <p className="leading-relaxed">
                  Paper trading has inherent limitations that users should be aware of:
                </p>
                <ul className="list-disc space-y-2 pl-6">
                  <li>
                    <strong className="text-foreground">No Emotional Factor:</strong> Paper trading 
                    eliminates the psychological pressure of risking real money, which is a crucial 
                    factor in real trading.
                  </li>
                  <li>
                    <strong className="text-foreground">Perfect Execution:</strong> Paper trades may 
                    execute at prices that would not be available in real markets.
                  </li>
                  <li>
                    <strong className="text-foreground">No Liquidity Constraints:</strong> Real markets 
                    may have insufficient liquidity for certain trades.
                  </li>
                  <li>
                    <strong className="text-foreground">Results May Not Translate:</strong> Success in 
                    paper trading does not guarantee success in real trading.
                  </li>
                </ul>
              </div>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">Third-Party Content</h2>
              <p className="text-muted-foreground leading-relaxed">
                This Platform may display market data from third-party providers. We do not guarantee 
                the accuracy, completeness, or timeliness of such data. Any reliance on this information 
                is at your own risk.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">Regulatory Compliance</h2>
              <p className="text-muted-foreground leading-relaxed">
                OptionSim is not a registered broker-dealer, investment advisor, or financial services 
                provider. This Platform is not regulated by SEBI, NSE, BSE, or any other financial 
                regulatory authority. Users are responsible for ensuring compliance with all applicable 
                laws and regulations in their jurisdiction.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">No Liability</h2>
              <p className="text-muted-foreground leading-relaxed">
                We expressly disclaim any and all liability for any losses, damages, or other consequences 
                arising from decisions made based on the use of this Platform. Users are solely responsible 
                for any real trading decisions they make outside of this Platform.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">Contact</h2>
              <p className="text-muted-foreground leading-relaxed">
                If you have questions about this Disclaimer, please contact us at:{" "}
                <a href="mailto:legal@optionsim.demo" className="text-primary hover:underline">
                  legal@optionsim.demo
                </a>
              </p>
            </section>

            {/* Final Warning */}
            <section className="rounded-lg border-2 border-loss/30 bg-loss/10 p-6">
              <p className="text-center font-semibold text-loss">
                ⚠️ Never invest real money based solely on paper trading results. 
                Always consult a qualified financial professional before making investment decisions.
              </p>
            </section>
          </div>
        </motion.div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-8">
        <div className="mx-auto max-w-4xl px-4 text-center text-sm text-muted-foreground sm:px-6 lg:px-8">
          © 2026 OptionSim. All rights reserved.
        </div>
      </footer>
    </div>
  );
};

export default DisclaimerPage;
