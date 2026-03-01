import { apiFetch } from "./client";
import type { User, LoginResponse } from "@/types/auth";

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  const data = await apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  // Store token
  if (data.token) {
    localStorage.setItem("auth_token", data.token);
    document.cookie = `auth_token=${encodeURIComponent(data.token)}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
  }

  return data;
}

export async function register(
  email: string,
  password: string,
  display_name: string
): Promise<{ user: User }> {
  return apiFetch<{ user: User }>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name }),
  });
}

export async function verifyEmail(
  token: string
): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>("/api/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export async function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export function logout() {
  localStorage.removeItem("auth_token");
  document.cookie = "auth_token=; path=/; max-age=0";
  window.location.href = "/login";
}
