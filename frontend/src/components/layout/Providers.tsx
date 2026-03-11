"use client";

import { AuthProvider } from "@/hooks/useAuth";
import { ThemeModeProvider } from "@/hooks/useThemeMode";
import { TradingModeProvider } from "@/hooks/useTradingMode";
import { ToastProvider } from "@/components/ui/toast";

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
