"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Settings } from "lucide-react";

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

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <header className="border-b border-border/50 bg-background/80 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-stretch">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-2.5 shrink-0 mr-8">
          <div className="h-7 w-7 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Activity className="h-4 w-4 text-primary" />
          </div>
          <span className="font-semibold text-[15px] tracking-tight text-foreground">
            Adaptive Trading
          </span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-stretch">
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

        {/* Settings */}
        <div className="ml-auto flex items-center">
          <Link
            href="/settings"
            aria-label="Settings"
            className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <Settings className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </header>
  );
}
