import React from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowLeft, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";

const PrivacyPolicyPage: React.FC = () => {
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
              <Shield className="h-7 w-7 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">Privacy Policy</h1>
              <p className="text-muted-foreground">Last updated: January 17, 2026</p>
            </div>
          </div>

          <div className="prose prose-invert max-w-none space-y-8">
            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">1. Introduction</h2>
              <p className="text-muted-foreground leading-relaxed">
                Welcome to OptionSim ("we," "our," or "us"). This Privacy Policy explains how we collect, 
                use, disclose, and safeguard your information when you use our paper trading simulator 
                platform. Please read this privacy policy carefully.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">2. Information We Collect</h2>
              <div className="space-y-4 text-muted-foreground">
                <div>
                  <h3 className="font-medium text-foreground">Personal Information</h3>
                  <p className="mt-2 leading-relaxed">
                    When you create an account, we may collect your name, email address, and Google account 
                    information if you choose to sign in with Google.
                  </p>
                </div>
                <div>
                  <h3 className="font-medium text-foreground">Usage Data</h3>
                  <p className="mt-2 leading-relaxed">
                    We automatically collect information about your interactions with our platform, including 
                    paper trades executed, portfolio performance, and feature usage patterns.
                  </p>
                </div>
                <div>
                  <h3 className="font-medium text-foreground">Device Information</h3>
                  <p className="mt-2 leading-relaxed">
                    We may collect information about your device, including IP address, browser type, 
                    operating system, and device identifiers.
                  </p>
                </div>
              </div>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">3. How We Use Your Information</h2>
              <ul className="list-disc space-y-2 pl-6 text-muted-foreground">
                <li>To provide and maintain our paper trading simulator</li>
                <li>To process your paper trades and track your virtual portfolio</li>
                <li>To analyze usage patterns and improve our platform</li>
                <li>To communicate with you about updates and features</li>
                <li>To detect and prevent fraud or misuse</li>
                <li>To comply with legal obligations</li>
              </ul>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">4. Data Security</h2>
              <p className="text-muted-foreground leading-relaxed">
                We implement appropriate technical and organizational security measures to protect your 
                personal information. However, no method of transmission over the Internet is 100% secure, 
                and we cannot guarantee absolute security.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">5. Third-Party Services</h2>
              <p className="text-muted-foreground leading-relaxed">
                We may use third-party services for authentication (Google OAuth), market data feeds, 
                and analytics. These services have their own privacy policies governing the use of your 
                information.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">6. Data Retention</h2>
              <p className="text-muted-foreground leading-relaxed">
                We retain your personal information for as long as your account is active or as needed 
                to provide you services. You may request deletion of your account and associated data 
                at any time.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">7. Your Rights</h2>
              <ul className="list-disc space-y-2 pl-6 text-muted-foreground">
                <li>Access and receive a copy of your personal data</li>
                <li>Rectify inaccurate personal data</li>
                <li>Request deletion of your personal data</li>
                <li>Object to processing of your personal data</li>
                <li>Data portability</li>
              </ul>
            </section>

            <section className="rounded-lg border border-border bg-card p-6">
              <h2 className="mb-4 text-xl font-semibold text-foreground">8. Contact Us</h2>
              <p className="text-muted-foreground leading-relaxed">
                If you have questions about this Privacy Policy, please contact us at:{" "}
                <a href="mailto:privacy@optionsim.demo" className="text-primary hover:underline">
                  privacy@optionsim.demo
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

export default PrivacyPolicyPage;
