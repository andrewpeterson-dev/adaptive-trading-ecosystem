import { apiFetch } from "./client";
import type {
  AuthActionResponse,
  LoginResponse,
  PasswordResetRequestResponse,
  RegisterResponse,
  User,
  WebSocketTokenResponse,
} from "@/types/auth";

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
    timeoutMs: 12_000,
  });
}

export async function register(
  email: string,
  password: string,
  display_name: string
): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, display_name }),
  });
}

export async function verifyEmail(
  token: string
): Promise<AuthActionResponse> {
  return apiFetch<AuthActionResponse>(
    `/api/auth/verify-email?token=${encodeURIComponent(token)}`
  );
}

export async function resendVerification(
  email: string
): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>("/api/auth/resend-verification", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function requestPasswordReset(
  email: string
): Promise<PasswordResetRequestResponse> {
  return apiFetch<PasswordResetRequestResponse>("/api/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function confirmPasswordReset(
  token: string,
  password: string
): Promise<AuthActionResponse> {
  return apiFetch<AuthActionResponse>("/api/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export async function getWebSocketToken(): Promise<WebSocketTokenResponse> {
  return apiFetch<WebSocketTokenResponse>("/api/auth/websocket-token", {
    method: "POST",
  });
}

export async function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export async function logout(): Promise<void> {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.removeItem("auth_token");
    } catch {
      // ignore storage access errors
    }
  }
  document.cookie = "auth_token=; path=/; max-age=0";
  try {
    await apiFetch("/api/auth/logout", { method: "DELETE" });
  } catch {
    // Even if the session is already invalid, continue to the login screen.
  }
  window.location.href = "/login";
}
