"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import React from "react";

export type TradingMode = "paper" | "live";

interface TradingModeContextValue {
  mode: TradingMode;
  setMode: (mode: TradingMode) => void;
  isPaper: boolean;
  isLive: boolean;
}

const TradingModeContext = createContext<TradingModeContextValue | null>(null);

const STORAGE_KEY = "trading_mode";

// paper = light theme, live = dark theme
function applyTheme(mode: TradingMode) {
  if (mode === "live") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
}

export function TradingModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<TradingMode>("paper");

  // Load persisted mode on mount and apply theme
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    const initial: TradingMode = stored === "live" ? "live" : "paper";
    setModeState(initial);
    applyTheme(initial);
  }, []);

  const setMode = useCallback((next: TradingMode) => {
    setModeState(next);
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }, []);

  const value: TradingModeContextValue = {
    mode,
    setMode,
    isPaper: mode === "paper",
    isLive: mode === "live",
  };

  return React.createElement(TradingModeContext.Provider, { value }, children);
}

export function useTradingMode(): TradingModeContextValue {
  const ctx = useContext(TradingModeContext);
  if (!ctx) {
    throw new Error("useTradingMode must be used within a TradingModeProvider");
  }
  return ctx;
}
