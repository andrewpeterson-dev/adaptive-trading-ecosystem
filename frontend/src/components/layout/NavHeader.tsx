"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import Image from "next/image";
import { Settings, Menu, X, LogOut } from "lucide-react";
import { useTradingMode } from "@/hooks/useTradingMode";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "Builder" },
  { href: "/strategies", label: "Strategies" },
  { href: "/bots", label: "Bots" },
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
  const { user, logout } = useAuth();

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <header className="sticky top-0 z-50 px-4 pt-4 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1440px]">
        <div className="app-panel px-4 py-3 sm:px-5">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex min-w-0 items-center gap-3">
              <div className="app-card flex h-11 w-11 shrink-0 items-center justify-center rounded-[18px]">
                <Image
                  src="/logo.png"
                  alt="Adaptive Trading"
                  width={28}
                  height={28}
                  className="h-7 w-7 object-contain"
                  priority
                />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold tracking-tight text-foreground">
                  Adaptive Trading
                </p>
                <p className="hidden text-xs text-muted-foreground sm:block">
                  Strategy design, intelligence, and execution
                </p>
              </div>
            </Link>

            <nav className="ml-4 hidden flex-1 justify-center xl:flex">
              <div className="app-segmented">
                {NAV_ITEMS.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "app-segment text-[13px] tracking-tight",
                      isActive(item.href)
                        ? "app-toggle-active"
                        : "text-muted-foreground"
                    )}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            </nav>

            <div className="ml-auto flex items-center gap-2">
              <div className="app-segmented hidden lg:flex">
                {(["paper", "live"] as const).map((targetMode) => {
                  const active = mode === targetMode;

                  return (
                    <button
                      key={targetMode}
                      type="button"
                      onClick={() => setMode(targetMode)}
                      disabled={switching || active}
                      className={cn(
                        "app-segment text-[11px] font-semibold uppercase tracking-[0.18em]",
                        active
                          ? targetMode === "live"
                            ? "border border-emerald-500/25 bg-emerald-500/12 text-emerald-300"
                            : "app-toggle-active"
                          : "text-muted-foreground",
                        switching && "opacity-60"
                      )}
                    >
                      <span
                        className={cn(
                          "h-2 w-2 rounded-full",
                          active
                            ? targetMode === "live"
                              ? "bg-emerald-400"
                              : "bg-current"
                            : "bg-muted-foreground/40"
                        )}
                      />
                      {targetMode}
                    </button>
                  );
                })}
              </div>

              {user?.email && (
                <div className="app-pill hidden max-w-[220px] px-3 py-2 text-[11px] font-medium 2xl:block">
                  <span className="block truncate font-mono">{user.email}</span>
                </div>
              )}

              <Link
                href="/settings"
                aria-label="Settings"
                className="app-button-icon"
              >
                <Settings className="h-4 w-4" />
              </Link>
              <button
                onClick={logout}
                aria-label="Log out"
                title="Log out"
                className="app-button-icon hidden sm:inline-flex"
              >
                <LogOut className="h-4 w-4" />
              </button>
              <button
                onClick={() => setMenuOpen((open) => !open)}
                aria-label={menuOpen ? "Close menu" : "Open menu"}
                className="app-button-icon xl:hidden"
              >
                {menuOpen ? (
                  <X className="h-4.5 w-4.5" />
                ) : (
                  <Menu className="h-4.5 w-4.5" />
                )}
              </button>
            </div>
          </div>
        </div>

        {menuOpen && (
          <div className="app-panel mt-3 p-3 xl:hidden">
            <nav className="grid gap-2">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-2xl px-4 py-3 text-sm font-medium transition-colors",
                    isActive(item.href)
                      ? "app-card text-foreground"
                      : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <div className="mt-3 grid gap-3 border-t border-border/60 pt-3 sm:grid-cols-[1fr_auto_auto] sm:items-center">
              <div className="grid grid-cols-2 gap-2">
                {(["paper", "live"] as const).map((targetMode) => {
                  const active = mode === targetMode;

                  return (
                    <button
                      key={targetMode}
                      type="button"
                      onClick={() => setMode(targetMode)}
                      disabled={switching || active}
                      className={cn(
                        "app-inset rounded-2xl px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition-all",
                        active
                          ? targetMode === "live"
                            ? "border-emerald-500/25 bg-emerald-500/12 text-emerald-300"
                            : "border-primary/20 bg-primary/12 text-primary"
                          : "border-border/60 text-muted-foreground"
                      )}
                    >
                      {targetMode}
                    </button>
                  );
                })}
              </div>

              <Link
                href="/settings"
                className="app-button-secondary justify-center px-4 py-2 text-xs"
              >
                <Settings className="h-4 w-4" />
                Settings
              </Link>
              <button
                onClick={logout}
                className="app-button-secondary justify-center px-4 py-2 text-xs"
              >
                <LogOut className="h-4 w-4" />
                Log Out
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
