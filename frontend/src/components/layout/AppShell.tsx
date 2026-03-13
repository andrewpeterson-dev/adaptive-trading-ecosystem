"use client";

import dynamic from "next/dynamic";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

function HeaderPlaceholder() {
  return (
    <div className="px-4 pt-4 sm:px-6 lg:px-8" aria-hidden="true">
      <div className="mx-auto max-w-[1440px]">
        <div className="app-panel h-[92px] px-4 py-3 opacity-0 sm:h-[96px] sm:px-5" />
      </div>
    </div>
  );
}

const NavHeader = dynamic(
  () => import("@/components/layout/NavHeader").then((m) => m.NavHeader),
  {
    ssr: false,
    loading: () => <HeaderPlaceholder />,
  }
);

// Lazy-load heavy Cerberus components — they include markdown renderer,
// chart libraries, and WebSocket logic that aren't needed at initial paint.
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

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute inset-x-0 top-[-18rem] h-[42rem] bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.22),transparent_50%)] dark:bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.18),transparent_45%)]" />
        <div className="absolute inset-y-0 right-[-10rem] w-[34rem] bg-[radial-gradient(circle_at_center,rgba(125,211,252,0.18),transparent_58%)] dark:bg-[radial-gradient(circle_at_center,rgba(103,232,249,0.1),transparent_56%)]" />
        <div className="absolute inset-y-0 left-[-12rem] w-[36rem] bg-[radial-gradient(circle_at_center,rgba(148,163,184,0.12),transparent_58%)] dark:bg-[radial-gradient(circle_at_center,rgba(30,41,59,0.32),transparent_55%)]" />
      </div>

      {!isAuthRoute && <NavHeader />}

      <main
        className={cn(
          isAuthRoute
            ? "min-h-screen"
            : "mx-auto max-w-[1440px] px-4 pb-12 pt-5 sm:px-6 sm:pb-16 sm:pt-6 lg:px-8 lg:pt-7"
        )}
      >
        {children}
      </main>

      {!isAuthRoute && (
        <>
          <AIWidget />
          <ConfirmationModal />
        </>
      )}
    </div>
  );
}
