"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LogOut,
  Menu,
  Settings,
  ShieldAlert,
  X,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useTradingMode } from "@/hooks/useTradingMode";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

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
  const [confirmLiveOpen, setConfirmLiveOpen] = useState(false);
  const { mode, setMode, switching } = useTradingMode();
  const { user, logout } = useAuth();

  useEffect(() => {
    setMenuOpen(false);
  }, [pathname]);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const handleModeRequest = (targetMode: "paper" | "live") => {
    if (switching || mode === targetMode) return;
    if (targetMode === "live") {
      setConfirmLiveOpen(true);
      return;
    }
    setMode(targetMode);
  };

  return (
    <TooltipProvider delayDuration={150}>
      <header className="sticky top-0 z-50 px-4 pt-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-[1440px]">
          <div className="app-panel px-4 py-3 sm:px-5">
            <div className="flex flex-wrap items-center gap-4 xl:flex-nowrap">
              <Link href="/" className="flex min-w-0 items-center gap-3">
                <div className="app-card flex h-14 w-14 shrink-0 items-center justify-center rounded-[22px]">
                  <Image
                    src="/favicon.svg"
                    alt="Adaptive Trading"
                    width={28}
                    height={28}
                    className="h-7 w-7 object-contain"
                    priority
                  />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-base font-semibold tracking-tight text-foreground">
                      Adaptive Trading
                    </p>
                    <span className="hidden rounded-full border border-sky-400/20 bg-sky-400/8 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-400 sm:inline-flex">
                      Cerberus
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">Strategy workspace</p>
                </div>
              </Link>

              <nav className="hidden min-w-0 flex-1 lg:flex">
                <div className="flex w-full flex-wrap items-center justify-center gap-1.5 rounded-[24px] border border-border/65 bg-muted/24 px-3 py-2">
                  {NAV_ITEMS.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "rounded-full px-4 py-2.5 text-[13px] font-medium tracking-tight transition-all",
                        isActive(item.href)
                          ? "border border-primary/20 bg-primary/12 text-primary shadow-[0_14px_26px_-22px_rgba(59,130,246,0.55)]"
                          : "text-muted-foreground hover:bg-muted/35 hover:text-foreground"
                      )}
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
              </nav>

              <div className="ml-auto flex items-center gap-2">
                <div className="hidden items-center gap-2 rounded-[22px] border border-border/60 bg-muted/30 px-2 py-1.5 xl:flex">
                  <div className="px-2">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Live Trading
                    </p>
                    <p
                      className={cn(
                        "mt-1 text-xs font-semibold uppercase tracking-[0.14em]",
                        mode === "live" ? "text-emerald-400" : "text-amber-400"
                      )}
                    >
                      {mode === "live" ? "ON" : "OFF"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleModeRequest("paper")}
                    disabled={switching || mode === "paper"}
                    className={cn(
                      "app-segment text-[11px] font-semibold uppercase tracking-[0.18em]",
                      mode === "paper"
                        ? "app-toggle-active"
                        : "text-muted-foreground",
                      switching && "opacity-60"
                    )}
                  >
                    Paper
                  </button>
                  <button
                    type="button"
                    onClick={() => handleModeRequest("live")}
                    disabled={switching}
                    className={cn(
                      "app-segment text-[11px] font-semibold uppercase tracking-[0.18em]",
                      mode === "live"
                        ? "border border-emerald-500/25 bg-emerald-500/12 text-emerald-300"
                        : "border border-amber-500/20 bg-amber-500/8 text-amber-500 dark:text-amber-300",
                      switching && "opacity-60"
                    )}
                  >
                    {mode === "live" ? "Live On" : "Enable Live"}
                  </button>
                </div>

                {user?.email && (
                  <div className="app-pill hidden max-w-[220px] px-3 py-2 text-[11px] font-medium 2xl:block">
                    <span className="block truncate font-mono">{user.email}</span>
                  </div>
                )}

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Link
                      href="/settings"
                      aria-label="Settings"
                      className="app-button-icon"
                    >
                      <Settings className="h-4 w-4" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent>Settings</TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={logout}
                      aria-label="Log out"
                      className="app-button-icon hidden sm:inline-flex"
                    >
                      <LogOut className="h-4 w-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent>Log out</TooltipContent>
                </Tooltip>

                <button
                  onClick={() => setMenuOpen((open) => !open)}
                  aria-label={menuOpen ? "Close menu" : "Open menu"}
                  className="app-button-icon lg:hidden"
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
            <div className="app-panel mt-3 p-3 lg:hidden">
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

              <div className="mt-3 space-y-3 border-t border-border/60 pt-3">
                <div className="rounded-[20px] border border-border/60 bg-muted/30 p-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        Live Trading
                      </p>
                      <p
                        className={cn(
                          "mt-1 text-sm font-semibold",
                          mode === "live" ? "text-emerald-400" : "text-amber-400"
                        )}
                      >
                        {mode === "live" ? "LIVE ON" : "LIVE OFF"}
                      </p>
                    </div>
                    <ShieldAlert className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => handleModeRequest("paper")}
                      disabled={switching || mode === "paper"}
                      className={cn(
                        "app-inset rounded-2xl px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition-all",
                        mode === "paper"
                          ? "border-primary/20 bg-primary/12 text-primary"
                          : "border-border/60 text-muted-foreground"
                      )}
                    >
                      Paper
                    </button>
                    <button
                      type="button"
                      onClick={() => handleModeRequest("live")}
                      disabled={switching}
                      className={cn(
                        "app-inset rounded-2xl px-3 py-2 text-xs font-semibold uppercase tracking-[0.18em] transition-all",
                        mode === "live"
                          ? "border-emerald-500/25 bg-emerald-500/12 text-emerald-300"
                          : "border-amber-500/20 bg-amber-500/8 text-amber-500 dark:text-amber-300"
                      )}
                    >
                      {mode === "live" ? "Live On" : "Enable Live"}
                    </button>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
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
            </div>
          )}
        </div>
      </header>

      <Dialog open={confirmLiveOpen} onOpenChange={setConfirmLiveOpen}>
        <DialogContent className="max-w-md border border-amber-500/20 bg-card">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-foreground">
              <ShieldAlert className="h-5 w-5 text-amber-400" />
              Enable Live Trading
            </DialogTitle>
            <DialogDescription className="pt-2 text-sm leading-6 text-muted-foreground">
              Live mode routes orders against your real brokerage connection. Keep Cerberus in paper mode until you are ready for real capital exposure.
            </DialogDescription>
          </DialogHeader>

          <div className="rounded-[20px] border border-amber-500/15 bg-amber-500/6 p-4 text-sm text-muted-foreground">
            Current execution state:{" "}
            <span className="font-semibold text-foreground">LIVE OFF</span>
          </div>

          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmLiveOpen(false)}
              className="app-button-ghost"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                setConfirmLiveOpen(false);
                setMode("live");
              }}
              disabled={switching}
              className="rounded-full border border-emerald-500/25 bg-emerald-500/12 px-5 py-2.5 text-sm font-semibold text-emerald-300 transition-colors hover:border-emerald-400/35 hover:bg-emerald-500/18 disabled:opacity-50"
            >
              Confirm Live
            </button>
          </div>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  );
}
