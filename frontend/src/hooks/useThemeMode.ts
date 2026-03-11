"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import React from "react";

export type ThemeMode = "light" | "dark";

interface ThemeModeContextValue {
  theme: ThemeMode;
  isDark: boolean;
  toggleTheme: () => void;
  setTheme: (theme: ThemeMode) => void;
}

const ThemeModeContext = createContext<ThemeModeContextValue | null>(null);
const STORAGE_KEY = "workspace_theme";

function applyTheme(theme: ThemeMode): void {
  const html = document.documentElement;
  if (theme === "dark") {
    html.classList.add("dark");
  } else {
    html.classList.remove("dark");
  }
}

export function ThemeModeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>("dark");

  useEffect(() => {
    localStorage.removeItem(STORAGE_KEY);
    setThemeState("dark");
    applyTheme("dark");
  }, []);

  const setTheme = useCallback((next: ThemeMode) => {
    setThemeState("dark");
    localStorage.removeItem(STORAGE_KEY);
    applyTheme("dark");
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme("dark");
  }, [setTheme]);

  return React.createElement(
    ThemeModeContext.Provider,
    {
      value: {
        theme,
        isDark: theme === "dark",
        toggleTheme,
        setTheme,
      },
    },
    children
  );
}

export function useThemeMode(): ThemeModeContextValue {
  const ctx = useContext(ThemeModeContext);
  if (!ctx) {
    throw new Error("useThemeMode must be used within a ThemeModeProvider");
  }
  return ctx;
}
