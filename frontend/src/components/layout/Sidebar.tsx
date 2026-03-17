"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Blocks,
  Shield,
  Bot,
  LayoutDashboard,
  CandlestickChart,
  Brain,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  LogOut,
  Moon,
  Sun,
  User,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useThemeMode } from "@/hooks/useThemeMode";
import { useTradingMode } from "@/hooks/useTradingMode";
import { cn } from "@/lib/utils";
import { BrandLogo } from "./BrandLogo";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const NAV_ITEMS = [
  { href: "/strategy-builder", label: "Builder", icon: Blocks, activeFor: ["/strategy-builder"] },
  { href: "/strategies", label: "Strategies", icon: Shield, activeFor: ["/strategies"] },
  { href: "/bots", label: "Bots", icon: Bot, activeFor: ["/bots"] },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, activeFor: ["/dashboard", "/portfolio", "/risk"] },
  { href: "/trade", label: "Trade", icon: CandlestickChart, activeFor: ["/trade", "/trade-analysis", "/watchlist"] },
  { href: "/ai-intelligence", label: "Intelligence", icon: Brain, activeFor: ["/ai-intelligence", "/sentiment", "/models", "/quant"] },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useThemeMode();
  const { mode } = useTradingMode();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("sidebar_collapsed");
    if (saved !== null) {
      // Respect user's saved preference
      setCollapsed(saved === "true");
    } else if (typeof window !== "undefined" && window.innerWidth < 1280) {
      // First visit on small desktop — auto-collapse
      setCollapsed(true);
      localStorage.setItem("sidebar_collapsed", "true");
    }
  }, []);

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem("sidebar_collapsed", String(next));
      window.dispatchEvent(new CustomEvent("sidebar-toggle", { detail: { collapsed: next } }));
      return next;
    });
  };

  const isActive = (item: (typeof NAV_ITEMS)[number]) => {
    if (!pathname) return false;
    return item.activeFor.some((route) =>
      route === "/" ? pathname === "/" : pathname.startsWith(route)
    );
  };

  const ThemeIcon = theme === "dark" ? Sun : Moon;

  return (
    <TooltipProvider delayDuration={100}>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-[var(--status-bar-height)] bottom-0 z-40 hidden flex-col border-r border-border/60 bg-card/98 backdrop-blur-xl lg:flex sidebar-transition",
          collapsed ? "w-[var(--sidebar-collapsed-width)]" : "w-[var(--sidebar-width)]"
        )}
      >
        {/* Logo section */}
        <div className={cn(
          "flex items-center gap-3 border-b border-border/50 px-3 py-4",
          collapsed && "justify-center px-2"
        )}>
          <div className="flex h-8 w-8 shrink-0 items-center justify-center">
            <BrandLogo size={28} className="h-7 w-7" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold tracking-tight text-foreground">
                Adaptive Trading
              </p>
            </div>
          )}
        </div>

        {/* Navigation items */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
          {NAV_ITEMS.map((item) => {
            const active = isActive(item);
            const Icon = item.icon;

            const link = (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all",
                  collapsed && "justify-center px-2",
                  active
                    ? "bg-primary/12 text-primary"
                    : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                )}
              >
                <Icon className={cn("h-[18px] w-[18px] shrink-0", active && "text-primary")} />
                {!collapsed && (
                  <span className="truncate">{item.label}</span>
                )}
              </Link>
            );

            if (collapsed) {
              return (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>{link}</TooltipTrigger>
                  <TooltipContent side="right" sideOffset={8}>
                    {item.label}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return link;
          })}
        </nav>

        {/* Bottom section: trading mode + user + collapse toggle */}
        <div className="mt-auto border-t border-border/50">
          {/* Live Trading status */}
          <div className={cn(
            "flex items-center gap-2 border-b border-border/40 px-3 py-3",
            collapsed && "justify-center px-2"
          )}>
            <span
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                mode === "live"
                  ? "bg-emerald-400 animate-pulse-dot"
                  : "bg-amber-400"
              )}
            />
            {!collapsed && (
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  {mode === "live" ? "Live" : "Paper"}
                </p>
              </div>
            )}
          </div>

          {/* User & actions */}
          <div className={cn(
            "flex items-center gap-2 px-3 py-3",
            collapsed && "flex-col px-2"
          )}>
            {!collapsed ? (
              <>
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/12 text-primary">
                  <User className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-foreground">
                    {user?.email?.split("@")[0] || "User"}
                  </p>
                  <p className="truncate text-[11px] text-muted-foreground">
                    {user?.email || ""}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button onClick={toggleTheme} className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/40 hover:text-foreground transition-colors">
                        <ThemeIcon className="h-3.5 w-3.5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>Toggle theme</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link href="/settings" className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/40 hover:text-foreground transition-colors">
                        <Settings className="h-3.5 w-3.5" />
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent>Settings</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button onClick={logout} className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/40 hover:text-foreground transition-colors">
                        <LogOut className="h-3.5 w-3.5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>Log out</TooltipContent>
                  </Tooltip>
                </div>
              </>
            ) : (
              <>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/12 text-primary">
                      <User className="h-4 w-4" />
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="right">{user?.email || "User"}</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Link href="/settings" className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/40 hover:text-foreground transition-colors">
                      <Settings className="h-3.5 w-3.5" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent side="right">Settings</TooltipContent>
                </Tooltip>
              </>
            )}
          </div>

          {/* Collapse toggle */}
          <div className={cn("border-t border-border/40 px-2 py-2", collapsed && "flex justify-center")}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={toggle}
                  className="flex w-full items-center justify-center gap-2 rounded-lg p-2 text-muted-foreground hover:bg-muted/40 hover:text-foreground transition-colors"
                >
                  {collapsed ? (
                    <PanelLeftOpen className="h-4 w-4" />
                  ) : (
                    <>
                      <PanelLeftClose className="h-4 w-4" />
                      <span className="text-xs">Collapse</span>
                    </>
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                {collapsed ? "Expand sidebar" : "Collapse sidebar"}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      </aside>

      {/* Mobile bottom tab bar */}
      <nav className="mobile-bottom-tabs lg:hidden">
        {NAV_ITEMS.slice(1, 6).map((item) => {
          const active = isActive(item);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-1 px-3 py-1.5 text-[10px] font-medium transition-colors",
                active ? "text-primary" : "text-muted-foreground"
              )}
            >
              <Icon className="h-5 w-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </TooltipProvider>
  );
}
