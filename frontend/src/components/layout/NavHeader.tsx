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
        <div className="rounded-[28px] border border-white/70 bg-white/80 px-4 py-3 shadow-[0_28px_90px_-54px_rgba(15,23,42,0.45)] backdrop-blur-2xl dark:border-white/10 dark:bg-white/[0.05] sm:px-5">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex min-w-0 items-center gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[18px] border border-white/60 bg-white/80 shadow-[0_14px_34px_-24px_rgba(15,23,42,0.45)] dark:border-white/10 dark:bg-white/[0.06]">
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
              <div className="flex items-center gap-1 rounded-full border border-black/5 bg-slate-950/[0.03] p-1 dark:border-white/10 dark:bg-white/[0.04]">
                {NAV_ITEMS.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "rounded-full px-4 py-2 text-[13px] font-medium tracking-tight transition-all",
                      isActive(item.href)
                        ? "bg-foreground text-background shadow-[0_12px_24px_-16px_rgba(15,23,42,0.5)]"
                        : "text-muted-foreground hover:bg-black/[0.04] hover:text-foreground dark:hover:bg-white/[0.05]"
                    )}
                  >
                    {item.label}
                  </Link>
                ))}
              </div>
            </nav>

            <div className="ml-auto flex items-center gap-2">
              <div className="hidden items-center rounded-full border border-black/5 bg-slate-950/[0.03] p-1 dark:border-white/10 dark:bg-white/[0.04] lg:flex">
                {(["paper", "live"] as const).map((targetMode) => {
                  const active = mode === targetMode;

                  return (
                    <button
                      key={targetMode}
                      type="button"
                      onClick={() => setMode(targetMode)}
                      disabled={switching || active}
                      className={cn(
                        "inline-flex items-center gap-2 rounded-full px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] transition-all",
                        active
                          ? targetMode === "live"
                            ? "bg-emerald-500/12 text-emerald-500 dark:text-emerald-300"
                            : "bg-foreground text-background"
                          : "text-muted-foreground hover:text-foreground",
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
                <div className="hidden max-w-[220px] rounded-full border border-black/5 bg-white/70 px-3 py-2 text-[11px] font-medium text-muted-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.55)] dark:border-white/10 dark:bg-white/[0.05] 2xl:block">
                  <span className="block truncate font-mono">{user.email}</span>
                </div>
              )}

              <Link
                href="/settings"
                aria-label="Settings"
                className="flex h-10 w-10 items-center justify-center rounded-full border border-black/5 bg-white/70 text-muted-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.55)] transition-colors hover:text-foreground dark:border-white/10 dark:bg-white/[0.05]"
              >
                <Settings className="h-4 w-4" />
              </Link>
              <button
                onClick={logout}
                aria-label="Log out"
                title="Log out"
                className="hidden h-10 w-10 items-center justify-center rounded-full border border-black/5 bg-white/70 text-muted-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.55)] transition-colors hover:text-foreground dark:border-white/10 dark:bg-white/[0.05] sm:flex"
              >
                <LogOut className="h-4 w-4" />
              </button>
              <button
                onClick={() => setMenuOpen((open) => !open)}
                aria-label={menuOpen ? "Close menu" : "Open menu"}
                className="flex h-10 w-10 items-center justify-center rounded-full border border-black/5 bg-white/70 text-muted-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.55)] transition-colors hover:text-foreground dark:border-white/10 dark:bg-white/[0.05] xl:hidden"
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
          <div className="mt-3 rounded-[24px] border border-white/70 bg-white/85 p-3 shadow-[0_26px_80px_-52px_rgba(15,23,42,0.42)] backdrop-blur-2xl dark:border-white/10 dark:bg-slate-950/80 xl:hidden">
            <nav className="grid gap-2">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-2xl px-4 py-3 text-sm font-medium transition-colors",
                    isActive(item.href)
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:bg-black/[0.04] hover:text-foreground dark:hover:bg-white/[0.05]"
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
                        "rounded-2xl px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition-all",
                        active
                          ? targetMode === "live"
                            ? "bg-emerald-500/12 text-emerald-500 dark:text-emerald-300"
                            : "bg-foreground text-background"
                          : "border border-border/60 text-muted-foreground"
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
