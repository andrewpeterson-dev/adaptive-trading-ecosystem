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
import type { RegisterResponse, User, AuthState } from "@/types/auth";
import * as authApi from "@/lib/api/auth";

interface AuthContextValue extends AuthState {
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    displayName: string
  ) => Promise<RegisterResponse>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const checkSession = useCallback(async () => {
    try {
      const currentUser = await authApi.getCurrentUser();
      setUser(currentUser);
    } catch (err: unknown) {
      const status = (err as { status?: number })?.status;
      if (status === 401 || status === 403) {
        setUser(null);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkSession();
  }, [checkSession]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await authApi.login(email, password);
    if (response.user) {
      setUser(response.user);
    }
  }, []);

  const register = useCallback(
    async (
      email: string,
      password: string,
      displayName: string
    ): Promise<RegisterResponse> => {
      const response = await authApi.register(email, password, displayName);
      if (response.user) {
        setUser(response.user);
      }
      return response;
    },
    []
  );

  const logout = useCallback(() => {
    setUser(null);
    return authApi.logout();
  }, []);

  const value: AuthContextValue = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      isAdmin: user?.is_admin ?? false,
      login,
      register,
      logout,
    }),
    [user, isLoading, login, register, logout]
  );

  return React.createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
