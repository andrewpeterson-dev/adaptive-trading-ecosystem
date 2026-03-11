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
import type { User, AuthState } from "@/types/auth";
import * as authApi from "@/lib/api/auth";

interface AuthContextValue extends AuthState {
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkSession = useCallback(async () => {
    try {
      const token =
        localStorage.getItem("auth_token") ||
        document.cookie.match(/(?:^|; )auth_token=([^;]*)/)?.[1];
      if (!token) {
        setIsLoading(false);
        return;
      }
      const currentUser = await authApi.getCurrentUser();
      setUser(currentUser);
    } catch (err: unknown) {
      // Only clear the token on explicit auth failures (401/403).
      // Network errors, timeouts, etc. should NOT log the user out.
      const status = (err as { status?: number })?.status;
      if (status === 401 || status === 403) {
        localStorage.removeItem("auth_token");
        document.cookie = "auth_token=; path=/; max-age=0";
      }
      // For all other errors (network down, 5xx) keep the token so the
      // user stays logged in and retries will succeed once the server is back.
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await authApi.login(email, password);
    setUser(response.user);
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      const response = await authApi.register(email, password, displayName);
      setUser(response.user);
    },
    []
  );

  const logout = useCallback(() => {
    setUser(null);
    authApi.logout();
  }, []);

  const value: AuthContextValue = useMemo(() => ({
    user,
    isAuthenticated: !!user,
    isLoading,
    isAdmin: user?.is_admin ?? false,
    login,
    register,
    logout,
  }), [user, isLoading, login, register, logout]);

  return React.createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
