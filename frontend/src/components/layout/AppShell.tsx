"use client";

import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TradingStatusBar } from "@/components/layout/TradingStatusBar";
import { cn } from "@/lib/utils";
import { AmbientIntelligenceLayer } from "@/components/ambient/AmbientIntelligenceLayer";

const AIWidget = dynamic(
  () => import("@/components/cerberus/AIWidget").then((m) => m.AIWidget),
  { ssr: false }
);
const ConfirmationModal = dynamic(
  () => import("@/components/cerberus/ConfirmationModal").then((m) => m.ConfirmationModal),
  { ssr: false }
);

const AUTH_ROUTES = new Set(["/login", "/register", "/forgot-password", "/reset-password", "/verify-email"]);

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuthRoute = pathname ? AUTH_ROUTES.has(pathname) : false;
  const [isHydrated, setIsHydrated] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Sync sidebar collapse state for content margin
  useEffect(() => {
    const saved = localStorage.getItem("sidebar_collapsed");
    if (saved === "true") setSidebarCollapsed(true);

    const handleStorage = (e: StorageEvent) => {
      if (e.key === "sidebar_collapsed") {
        setSidebarCollapsed(e.newValue === "true");
      }
    };
    window.addEventListener("storage", handleStorage);

    const handleSidebarToggle = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setSidebarCollapsed(detail?.collapsed ?? false);
    };
    window.addEventListener("sidebar-toggle", handleSidebarToggle);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("sidebar-toggle", handleSidebarToggle);
    };
  }, []);

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <AmbientIntelligenceLayer />

      {!isAuthRoute && (
        <>
          <TradingStatusBar />
          <Sidebar />
        </>
      )}

      <main
        className={cn(
          "relative z-[1]",
          isAuthRoute
            ? "min-h-screen"
            : cn(
                "min-h-screen pb-12 pt-5 content-transition sm:pb-16 sm:pt-6 lg:pt-7",
                /* Desktop: offset for sidebar + status bar */
                "pt-[calc(var(--status-bar-height)+1.25rem)] sm:pt-[calc(var(--status-bar-height)+1.5rem)] lg:pt-[calc(var(--status-bar-height)+1.75rem)]",
                /* Mobile: no sidebar offset, add bottom padding for tab bar */
                "px-4 sm:px-6 lg:px-8",
                "pb-24 lg:pb-16",
                sidebarCollapsed
                  ? "lg:ml-[var(--sidebar-collapsed-width)]"
                  : "lg:ml-[var(--sidebar-width)]"
              )
        )}
      >
        <div className={cn(!isAuthRoute && "mx-auto max-w-[1440px] page-enter")} key={pathname}>
          {children}
        </div>
      </main>

      {!isAuthRoute && isHydrated && (
        <>
          <AIWidget />
          <ConfirmationModal />
        </>
      )}
    </div>
  );
}
