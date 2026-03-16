"use client";

import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TradingStatusBar } from "@/components/layout/TradingStatusBar";
import { cn } from "@/lib/utils";

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

    // Also listen for direct changes via MutationObserver on localStorage
    const interval = setInterval(() => {
      const current = localStorage.getItem("sidebar_collapsed") === "true";
      setSidebarCollapsed(current);
    }, 200);

    return () => {
      window.removeEventListener("storage", handleStorage);
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute inset-x-0 top-[-18rem] h-[42rem] bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.22),transparent_50%)] dark:bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.18),transparent_45%)]" />
        <div className="absolute inset-y-0 right-[-10rem] w-[34rem] bg-[radial-gradient(circle_at_center,rgba(125,211,252,0.18),transparent_58%)] dark:bg-[radial-gradient(circle_at_center,rgba(103,232,249,0.1),transparent_56%)]" />
        <div className="absolute inset-y-0 left-[-12rem] w-[36rem] bg-[radial-gradient(circle_at_center,rgba(148,163,184,0.12),transparent_58%)] dark:bg-[radial-gradient(circle_at_center,rgba(30,41,59,0.32),transparent_55%)]" />
      </div>

      {!isAuthRoute && (
        <>
          <TradingStatusBar />
          <Sidebar />
        </>
      )}

      <main
        className={cn(
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
        <div className={cn(!isAuthRoute && "mx-auto max-w-[1440px]")}>
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
