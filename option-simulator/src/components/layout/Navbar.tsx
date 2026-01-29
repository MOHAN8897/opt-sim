import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { TrendingUp, Chrome, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/stores/authStore";
import { useState } from "react";

const Navbar: React.FC = () => {
  const { isAuthenticated, user, logout, isLoading } = useAuthStore();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleGoogleLogin = () => {
    // Temporary: Navigate directly to trade page (skip OAuth for now)
    navigate("/trade");
  };

  const navLinks = [
    { label: "Features", href: "#features" },
    { label: "How It Works", href: "#how-it-works" },
    { label: "Pricing", href: "#pricing" },
  ];

  return (
    <motion.nav
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      className="fixed top-0 left-0 right-0 z-50 border-b border-border/50 bg-background/80 backdrop-blur-xl"
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
            <TrendingUp className="h-5 w-5 text-primary" />
          </div>
          <span className="text-xl font-bold text-foreground">OptionSim</span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden items-center gap-8 md:flex">
          {navLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Auth Buttons */}
        <div className="hidden items-center gap-4 md:flex">
          {isLoading ? (
            <div className="h-10 w-28 animate-pulse rounded-md bg-muted" />
          ) : isAuthenticated ? (
            <>
              <Button
                variant="ghost"
                onClick={() => navigate("/")}
                className="text-sm"
              >
                Home
              </Button>
              <Button
                variant="ghost"
                onClick={() => navigate("/dashboard")}
                className="text-sm"
              >
                Dashboard
              </Button>
              <Button
                variant="outline"
                onClick={logout}
                className="text-sm"
              >
                Logout
              </Button>
            </>
          ) : (
            <Button
              onClick={handleGoogleLogin}
              className="btn-glow-primary gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
            >
              <Chrome className="h-4 w-4" />
              Continue with Google
            </Button>
          )}
        </div>

        {/* Mobile Menu Button */}
        <button
          className="md:hidden"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          {mobileMenuOpen ? (
            <X className="h-6 w-6 text-foreground" />
          ) : (
            <Menu className="h-6 w-6 text-foreground" />
          )}
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="border-t border-border/50 bg-background md:hidden"
        >
          <div className="space-y-2 px-4 py-4">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="block rounded-lg px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                onClick={() => setMobileMenuOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <div className="pt-4">
              {isLoading ? (
                <div className="space-y-2">
                  <div className="h-9 w-full animate-pulse rounded-md bg-muted" />
                </div>
              ) : isAuthenticated ? (
                <div className="space-y-2">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      navigate("/");
                      setMobileMenuOpen(false);
                    }}
                    className="w-full justify-start text-sm"
                  >
                    Home
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      navigate("/dashboard");
                      setMobileMenuOpen(false);
                    }}
                    className="w-full justify-start text-sm"
                  >
                    Dashboard
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      logout();
                      setMobileMenuOpen(false);
                    }}
                    className="w-full text-sm"
                  >
                    Logout
                  </Button>
                </div>
              ) : (
                <Button
                  onClick={handleGoogleLogin}
                  className="btn-glow-primary w-full gap-2 bg-primary text-primary-foreground hover:bg-primary/90"
                >
                  <Chrome className="h-4 w-4" />
                  Continue with Google
                </Button>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </motion.nav>
  );
};

export { Navbar };
