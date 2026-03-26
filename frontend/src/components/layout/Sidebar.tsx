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

/* ═══════════════════════════════════════════════════════════════════════════
   NAV — organised into labelled sections
   ═══════════════════════════════════════════════════════════════════════════ */

interface NavItem {
  href: string;
  label: string;
  icon: typeof Blocks;
  activeFor: string[];
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: "Build",
    items: [
      { href: "/strategy-builder", label: "Builder", icon: Blocks, activeFor: ["/strategy-builder"] },
      { href: "/strategies", label: "Strategies", icon: Shield, activeFor: ["/strategies"] },
      { href: "/bots", label: "Bots", icon: Bot, activeFor: ["/bots"] },
    ],
  },
  {
    title: "Execute",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, activeFor: ["/dashboard", "/portfolio", "/risk"] },
      { href: "/trade", label: "Trade", icon: CandlestickChart, activeFor: ["/trade", "/trade-analysis", "/watchlist"] },
    ],
  },
  {
    title: "AI",
    items: [
      { href: "/ai-intelligence", label: "Intelligence", icon: Brain, activeFor: ["/ai-intelligence", "/sentiment", "/models", "/quant"] },
    ],
  },
];

// Flat list for mobile tab bar
const ALL_NAV_ITEMS = NAV_SECTIONS.flatMap((s) => s.items);

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useThemeMode();
  const { mode } = useTradingMode();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("sidebar_collapsed");
    if (saved !== null) {
      setCollapsed(saved === "true");
    } else if (typeof window !== "undefined" && window.innerWidth < 1280) {
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

  const isActive = (item: NavItem) => {
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
          "fixed left-0 top-[var(--status-bar-height)] bottom-0 z-40 hidden flex-col border-r lg:flex sidebar-transition",
          collapsed ? "w-[var(--sidebar-collapsed-width)]" : "w-[var(--sidebar-width)]"
        )}
        style={{
          borderColor: "hsl(var(--border) / 0.4)",
          background: "linear-gradient(180deg, hsl(var(--surface-1) / 0.97), hsl(var(--surface-1) / 0.99))",
          backdropFilter: "blur(24px)",
        }}
      >
        {/* Logo section */}
        <div className={cn(
          "flex items-center gap-3 border-b px-3 py-4",
          collapsed && "justify-center px-2"
        )} style={{ borderColor: "hsl(var(--border) / 0.3)" }}>
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

        {/* Navigation sections */}
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {NAV_SECTIONS.map((section, si) => (
            <div key={section.title} className={cn(si > 0 && "mt-5")}>
              {/* Section header */}
              {!collapsed && (
                <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/50">
                  {section.title}
                </p>
              )}
              {collapsed && si > 0 && (
                <div className="mx-auto mb-2 mt-1 h-px w-5" style={{ background: "hsl(var(--border) / 0.3)" }} />
              )}

              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const active = isActive(item);
                  const Icon = item.icon;

                  const link = (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all duration-200",
                        collapsed && "justify-center px-2",
                        active
                          ? "text-primary"
                          : "text-muted-foreground hover:text-foreground"
                      )}
                      style={active ? {
                        background: "linear-gradient(135deg, hsl(var(--primary) / 0.12), hsl(var(--primary) / 0.06))",
                        boxShadow: "0 0 20px -4px hsl(var(--primary) / 0.15), inset 0 0 0 1px hsl(var(--primary) / 0.15)",
                      } : undefined}
                    >
                      {/* Active glow accent */}
                      {active && (
                        <span
                          className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r-full"
                          style={{ background: "hsl(var(--primary))", boxShadow: "0 0 8px 1px hsl(var(--primary) / 0.5)" }}
                        />
                      )}
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
              </div>
            </div>
          ))}
        </nav>

        {/* Bottom section: trading mode + user + collapse toggle */}
        <div className="mt-auto" style={{ borderTop: "1px solid hsl(var(--border) / 0.3)" }}>
          {/* Trading mode status */}
          <div className={cn(
            "flex items-center gap-2 px-3 py-3",
            collapsed && "justify-center px-2"
          )} style={{ borderBottom: "1px solid hsl(var(--border) / 0.2)" }}>
            <span
              className={cn(
                "h-2 w-2 shrink-0 rounded-full",
                mode === "live"
                  ? "bg-emerald-400 animate-pulse-dot"
                  : "bg-amber-400"
              )}
              style={mode === "live" ? { boxShadow: "0 0 6px 1px rgba(52,211,153,0.5)" } : { boxShadow: "0 0 6px 1px rgba(251,191,36,0.3)" }}
            />
            {!collapsed && (
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {mode === "live" ? "Live" : "Paper"} Mode
              </p>
            )}
          </div>

          {/* User & actions */}
          <div className={cn(
            "flex items-center gap-2 px-3 py-3",
            collapsed && "flex-col px-2"
          )}>
            {!collapsed ? (
              <>
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
                  style={{ background: "hsl(var(--primary) / 0.1)", border: "1px solid hsl(var(--primary) / 0.15)" }}>
                  <User className="h-4 w-4 text-primary" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-foreground">
                    {user?.email?.split("@")[0] || "User"}
                  </p>
                  <p className="truncate text-[11px] text-muted-foreground/60">
                    {user?.email || ""}
                  </p>
                </div>
                <div className="flex items-center gap-0.5">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button onClick={toggleTheme} className="rounded-lg p-1.5 text-muted-foreground/60 hover:bg-muted/30 hover:text-foreground transition-colors">
                        <ThemeIcon className="h-3.5 w-3.5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>Toggle theme</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link href="/settings" className="rounded-lg p-1.5 text-muted-foreground/60 hover:bg-muted/30 hover:text-foreground transition-colors">
                        <Settings className="h-3.5 w-3.5" />
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent>Settings</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button onClick={logout} className="rounded-lg p-1.5 text-muted-foreground/60 hover:bg-muted/30 hover:text-foreground transition-colors">
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
                    <div className="flex h-8 w-8 items-center justify-center rounded-full"
                      style={{ background: "hsl(var(--primary) / 0.1)", border: "1px solid hsl(var(--primary) / 0.15)" }}>
                      <User className="h-4 w-4 text-primary" />
                    </div>
                  </TooltipTrigger>
                  <TooltipContent side="right">{user?.email || "User"}</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Link href="/settings" className="rounded-lg p-1.5 text-muted-foreground/60 hover:bg-muted/30 hover:text-foreground transition-colors">
                      <Settings className="h-3.5 w-3.5" />
                    </Link>
                  </TooltipTrigger>
                  <TooltipContent side="right">Settings</TooltipContent>
                </Tooltip>
              </>
            )}
          </div>

          {/* Collapse toggle */}
          <div className={cn("px-2 py-2", collapsed && "flex justify-center")}
            style={{ borderTop: "1px solid hsl(var(--border) / 0.2)" }}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={toggle}
                  className="flex w-full items-center justify-center gap-2 rounded-lg p-2 text-muted-foreground/60 hover:bg-muted/30 hover:text-foreground transition-colors"
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
        {ALL_NAV_ITEMS.map((item) => {
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
