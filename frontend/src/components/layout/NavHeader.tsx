"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Image from "next/image";
import { Settings, Menu, X, LogOut } from "lucide-react";
import { useTradingMode } from "@/hooks/useTradingMode";
import { logout, getCurrentUser } from "@/lib/api/auth";

const NAV_ITEMS = [
  { href: "/", label: "Builder" },
  { href: "/strategies", label: "Strategies" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/trade", label: "Trade" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/models", label: "Models" },
  { href: "/risk", label: "Risk" },
  { href: "/quant", label: "Quant" },
];

export function NavHeader() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const { mode, setMode, switching } = useTradingMode();
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    getCurrentUser()
      .then((u) => setUserEmail(u.email))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <header className="border-b border-border/40 bg-background/90 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-[52px] flex items-center">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-2 shrink-0 mr-8 group">
          <Image src="/logo.png" alt="Adaptive Trading" width={28} height={28} className="h-7 w-7 object-contain" priority />
          <span className="font-semibold text-[14px] tracking-tight text-foreground">
            Adaptive Trading
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden lg:flex items-stretch h-[52px]">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`relative flex items-center px-3 text-[12px] font-medium tracking-wide transition-colors ${
                isActive(item.href)
                  ? "text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.label}
              {isActive(item.href) && (
                <span className="absolute bottom-0 left-2 right-2 h-[2px] rounded-full bg-primary" />
              )}
            </Link>
          ))}
        </nav>

        {/* Right controls */}
        <div className="ml-auto flex items-center gap-1.5">
          {/* Paper / Live toggle */}
          <button
            onClick={() => setMode(mode === "paper" ? "live" : "paper")}
            disabled={switching}
            aria-label={`Switch to ${mode === "paper" ? "live" : "paper"} trading`}
            title={`Currently: ${mode === "paper" ? "Paper" : "Live"} trading — click to switch`}
            className={`relative flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold tracking-widest uppercase border transition-all duration-200 ${
              mode === "live"
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
                : "bg-muted/60 border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted"
            } ${switching ? "opacity-50 cursor-wait" : ""}`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                mode === "live" ? "bg-emerald-400 animate-pulse" : "bg-muted-foreground/40"
              }`}
            />
            {mode === "paper" ? "Paper" : "Live"}
          </button>

          {userEmail && (
            <span className="hidden xl:block text-[10px] text-muted-foreground font-mono max-w-[140px] truncate px-1.5">
              {userEmail}
            </span>
          )}

          <Link
            href="/settings"
            aria-label="Settings"
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <Settings className="h-4 w-4" />
          </Link>
          <button
            onClick={logout}
            aria-label="Log out"
            title="Log out"
            className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            className="lg:hidden p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Dropdown */}
      {menuOpen && (
        <nav className="lg:hidden border-t border-border/40 bg-background/95 backdrop-blur-md">
          <div className="max-w-7xl mx-auto px-4 py-2 space-y-0.5">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center py-2.5 px-3 rounded-lg text-sm font-medium transition-colors ${
                  isActive(item.href)
                    ? "text-foreground bg-muted/60"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </nav>
      )}
    </header>
  );
}
