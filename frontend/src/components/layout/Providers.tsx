"use client";

import { AuthProvider } from "@/hooks/useAuth";
import { TradingModeProvider } from "@/hooks/useTradingMode";
import { ToastProvider } from "@/components/ui/toast";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <TradingModeProvider>
        <ToastProvider>{children}</ToastProvider>
      </TradingModeProvider>
    </AuthProvider>
  );
}
