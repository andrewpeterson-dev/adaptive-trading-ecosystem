"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from "react";
import React from "react";
import { getServerMode, setServerMode } from "@/lib/api/mode";

export type TradingMode = "paper" | "live";

interface TradingModeContextValue {
  mode: TradingMode;
  setMode: (mode: TradingMode) => Promise<void>;
  isPaper: boolean;
  isLive: boolean;
  switching: boolean;
}

const TradingModeContext = createContext<TradingModeContextValue | null>(null);

const STORAGE_KEY = "trading_mode";

/**
 * Broadcast a custom event so all polling hooks and components know to re-fetch.
 * Components listen via useModeResetListener().
 */
function broadcastModeReset(): void {
  window.dispatchEvent(new CustomEvent("trading-mode-reset"));
}

export function TradingModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<TradingMode>("paper");
  const [switching, setSwitching] = useState(false);

  // On mount: fetch server-authoritative mode
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as TradingMode | null;
    if (stored === "paper" || stored === "live") {
      setModeState(stored);
    }
    // Then confirm with server (source of truth)
    getServerMode()
      .then((serverMode) => {
        setModeState(serverMode);
        localStorage.setItem(STORAGE_KEY, serverMode);
      })
      .catch(() => {
        // Not logged in yet — keep localStorage value
      });
  }, []);

  const setMode = useCallback(async (next: TradingMode) => {
    setSwitching(true);
    try {
      // 1. Tell the server first (source of truth)
      await setServerMode(next);
      // 2. Only update client after server confirms
      setModeState(next);
      localStorage.setItem(STORAGE_KEY, next);
      // 3. Broadcast reset so all components re-fetch
      broadcastModeReset();
    } catch (err) {
      console.error("Failed to switch mode:", err);
      throw err instanceof Error ? err : new Error("Failed to switch mode");
    } finally {
      setSwitching(false);
    }
  }, []);

  const value: TradingModeContextValue = useMemo(() => ({
    mode,
    setMode,
    isPaper: mode === "paper",
    isLive: mode === "live",
    switching,
  }), [mode, setMode, switching]);

  return React.createElement(TradingModeContext.Provider, { value }, children);
}

export function useTradingMode(): TradingModeContextValue {
  const ctx = useContext(TradingModeContext);
  if (!ctx) {
    throw new Error("useTradingMode must be used within a TradingModeProvider");
  }
  return ctx;
}

/**
 * Hook for components to re-fetch data when mode switches.
 * Call this in any component that fetches mode-specific data.
 */
export function useModeResetListener(onReset: () => void): void {
  useEffect(() => {
    const handler = () => onReset();
    window.addEventListener("trading-mode-reset", handler);
    return () => window.removeEventListener("trading-mode-reset", handler);
  }, [onReset]);
}
