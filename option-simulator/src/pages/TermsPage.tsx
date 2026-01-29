import React from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowLeft, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";

const TermsPage: React.FC = () => {
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
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10">
              <FileText className="h-7 w-7 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">Terms of Service</h1>
              <p className="text-muted-foreground">Last updated: January 17, 2026</p>
            </div>
          </div>

          <div className="prose prose-invert max-w-none space-y-8">
            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">1. Acceptance of Terms</h2>
              <p className="text-muted-foreground leading-relaxed">
                By accessing or using OptionSim ("the Platform"), you agree to be bound by these Terms of 
                Service. If you do not agree to these terms, please do not use the Platform.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">2. Description of Service</h2>
              <p className="text-muted-foreground leading-relaxed">
                OptionSim is a paper trading simulator designed for educational purposes. The Platform 
                allows users to practice options trading strategies using virtual money and simulated 
                or delayed market data. No real financial transactions occur on this Platform.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">3. User Accounts</h2>
              <div className="space-y-4 text-muted-foreground">
                <p className="leading-relaxed">
                  To use certain features of the Platform, you must create an account. You agree to:
                </p>
                <ul className="list-disc space-y-2 pl-6">
                  <li>Provide accurate and complete registration information</li>
                  <li>Maintain the security of your account credentials</li>
                  <li>Notify us immediately of any unauthorized access</li>
                  <li>Accept responsibility for all activities under your account</li>
                </ul>
              </div>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">4. Virtual Trading</h2>
              <div className="space-y-4 text-muted-foreground">
                <p className="leading-relaxed">
                  All trades executed on the Platform are simulated paper trades using virtual currency. 
                  You understand and agree that:
                </p>
                <ul className="list-disc space-y-2 pl-6">
                  <li>No real money is involved in any transaction</li>
                  <li>Virtual profits and losses have no real-world financial value</li>
                  <li>Market data may be delayed, simulated, or differ from actual market conditions</li>
                  <li>Paper trading results may not reflect real trading performance</li>
                </ul>
              </div>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">5. Prohibited Conduct</h2>
              <p className="mb-4 text-muted-foreground">You agree not to:</p>
              <ul className="list-disc space-y-2 pl-6 text-muted-foreground">
                <li>Use the Platform for any illegal purpose</li>
                <li>Attempt to gain unauthorized access to any part of the Platform</li>
                <li>Interfere with or disrupt the Platform's operations</li>
                <li>Use automated scripts or bots without authorization</li>
                <li>Impersonate any person or entity</li>
                <li>Sell or transfer your account to another party</li>
              </ul>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">6. Intellectual Property</h2>
              <p className="text-muted-foreground leading-relaxed">
                All content on the Platform, including but not limited to text, graphics, logos, icons, 
                and software, is the property of OptionSim or its licensors and is protected by 
                intellectual property laws.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">7. Disclaimer of Warranties</h2>
              <p className="text-muted-foreground leading-relaxed">
                THE PLATFORM IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, 
                EXPRESS OR IMPLIED. WE DO NOT WARRANT THAT THE PLATFORM WILL BE UNINTERRUPTED, 
                ERROR-FREE, OR COMPLETELY SECURE.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">8. Limitation of Liability</h2>
              <p className="text-muted-foreground leading-relaxed">
                TO THE MAXIMUM EXTENT PERMITTED BY LAW, OPTIONSIM SHALL NOT BE LIABLE FOR ANY INDIRECT, 
                INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES ARISING FROM YOUR USE OF THE 
                PLATFORM.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">9. Modifications</h2>
              <p className="text-muted-foreground leading-relaxed">
                We reserve the right to modify these Terms of Service at any time. We will notify users 
                of significant changes. Continued use of the Platform after changes constitutes acceptance 
                of the modified terms.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">10. Contact Information</h2>
              <p className="text-muted-foreground leading-relaxed">
                For questions regarding these Terms of Service, please contact us at:{" "}
                <a href="mailto:legal@optionsim.demo" className="text-primary hover:underline">
                  legal@optionsim.demo
                </a>
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

export default TermsPage;
