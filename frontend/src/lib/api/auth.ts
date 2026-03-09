import { apiFetch } from "./client";
import type { User, LoginResponse } from "@/types/auth";

export type RegisterResponse = { token: string; user: User };

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
): Promise<RegisterResponse> {
  const data = await apiFetch<RegisterResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name }),
  });

  // Store token same as login
  if (data.token) {
    localStorage.setItem("auth_token", data.token);
    document.cookie = `auth_token=${encodeURIComponent(data.token)}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
  }

  return data;
}

// verifyEmail is not available — route /api/auth/verify-email does not exist.
// If email verification UI is needed, show a "not available" state instead of calling this.
export async function verifyEmail(
  _token: string
): Promise<{ success: boolean }> {
  return Promise.resolve({ success: false });
}

export async function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export function logout() {
  localStorage.removeItem("auth_token");
  document.cookie = "auth_token=; path=/; max-age=0";
  window.location.href = "/login";
}
