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
import { useThemeMode } from "@/hooks/useThemeMode";

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

function resolveStoredMode(): TradingMode {
  if (typeof window === "undefined") return "paper";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "live" ? "live" : "paper";
}

function themeForMode(mode: TradingMode): "light" | "dark" {
  return mode === "live" ? "dark" : "light";
}

/**
 * Broadcast a custom event so all polling hooks and components know to re-fetch.
 * Components listen via useModeResetListener().
 */
function broadcastModeReset(): void {
  window.dispatchEvent(new CustomEvent("trading-mode-reset"));
}

export function TradingModeProvider({ children }: { children: ReactNode }) {
  const { setTheme } = useThemeMode();
  const [mode, setModeState] = useState<TradingMode>(resolveStoredMode);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    getServerMode()
      .then((serverMode) => {
        setModeState(serverMode);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, mode);
    setTheme(themeForMode(mode));
  }, [mode, setTheme]);

  const setMode = useCallback(async (next: TradingMode) => {
    setSwitching(true);
    try {
      await setServerMode(next);
      setModeState(next);
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
