"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Settings, Menu, X } from "lucide-react";
import { useTradingMode } from "@/hooks/useTradingMode";

const NAV_ITEMS = [
  { href: "/", label: "Builder" },
  { href: "/strategies", label: "Strategies" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/trade", label: "Trade" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/models", label: "Models" },
  { href: "/risk", label: "Risk" },
];

export function NavHeader() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const { mode, setMode } = useTradingMode();

  // Auto-close menu on route change
  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <header className="border-b border-border/50 bg-background/80 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-2 shrink-0 mr-8">
          <Image
            src="/logo.png"
            alt="AI Trading"
            width={32}
            height={32}
            className="h-8 w-8 object-contain"
            priority
          />
          <span className="font-semibold text-[15px] tracking-tight text-foreground">
            AI Trading
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden lg:flex items-stretch h-14">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`relative flex items-center px-3 text-[13px] font-medium transition-colors ${
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

        {/* Settings + Hamburger */}
        <div className="ml-auto flex items-center gap-2">
          {/* Paper / Live toggle */}
          <button
            onClick={() => setMode(mode === "paper" ? "live" : "paper")}
            aria-label={`Switch to ${mode === "paper" ? "live" : "paper"} trading`}
            title={`Currently: ${mode === "paper" ? "Paper" : "Live"} trading — click to switch`}
            className={`relative flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wide border transition-all duration-200 ${
              mode === "live"
                ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/25"
                : "bg-muted/60 border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                mode === "live" ? "bg-emerald-400 animate-pulse" : "bg-muted-foreground/50"
              }`}
            />
            {mode === "paper" ? "Paper" : "Live"}
          </button>

          <Link
            href="/settings"
            aria-label="Settings"
            className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <Settings className="h-4 w-4" />
          </Link>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            className="lg:hidden p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Dropdown */}
      {menuOpen && (
        <nav className="lg:hidden border-t border-border/50 bg-background/95 backdrop-blur-md">
          <div className="max-w-7xl mx-auto px-4 py-2">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`block py-3 px-3 rounded-md text-sm font-medium transition-colors ${
                  isActive(item.href)
                    ? "text-foreground bg-muted/50"
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
