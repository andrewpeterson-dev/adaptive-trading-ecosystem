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
    } catch {
      // Token invalid or expired
      localStorage.removeItem("auth_token");
      document.cookie = "auth_token=; path=/; max-age=0";
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
      await authApi.register(email, password, displayName);
    },
    []
  );

  const logout = useCallback(() => {
    setUser(null);
    authApi.logout();
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: !!user,
    isLoading,
    isAdmin: user?.is_admin ?? false,
    login,
    register,
    logout,
  };

  return React.createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
