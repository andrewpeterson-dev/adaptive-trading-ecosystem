"use client";

import { AuthProvider } from "@/hooks/useAuth";
import { ThemeModeProvider } from "@/hooks/useThemeMode";
import { TradingModeProvider } from "@/hooks/useTradingMode";
import { ToastProvider } from "@/components/ui/toast";

// Migrate legacy "token" key → "access_token" so Bearer auth works on mutations
if (typeof window !== "undefined") {
  const legacy = window.localStorage.getItem("token");
  if (legacy && !window.localStorage.getItem("access_token")) {
    window.localStorage.setItem("access_token", legacy);
    window.localStorage.removeItem("token");
  }
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <ThemeModeProvider>
        <TradingModeProvider>
          <ToastProvider>{children}</ToastProvider>
        </TradingModeProvider>
      </ThemeModeProvider>
    </AuthProvider>
  );
}
