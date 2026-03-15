"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { AuthShell } from "@/components/layout/AuthShell";
import { ApiError } from "@/lib/api/client";

function LoginForm() {
  const searchParams = useSearchParams();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [needsVerification, setNeedsVerification] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNeedsVerification(false);
    setLoading(true);
    try {
      await login(email, password);
      const from = searchParams?.get("from");
      const destination = from && from.startsWith("/") ? from : "/dashboard";
      // Force a full navigation so middleware-protected routes see the fresh auth cookie immediately.
      window.location.assign(destination);
      return;
    } catch (err: unknown) {
      const message =
        err instanceof Error && err.message === "Request timed out"
          ? "Sign-in timed out. Please try again."
          : err instanceof Error
            ? err.message
            : "Login failed";
      if (
        err instanceof ApiError &&
        err.status === 403 &&
        email.trim() &&
        message.toLowerCase().includes("verify")
      ) {
        setNeedsVerification(true);
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      description="Access your strategies, broker connections, and Cerberus workspace from a cleaner control surface."
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-medium text-foreground">
            Create one
          </Link>
        </>
      }
    >
      <div className="space-y-5">
        {error && (
          <div className="rounded-[22px] border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}
        {needsVerification && (
          <div className="rounded-[22px] border border-amber-500/20 bg-amber-500/5 px-4 py-3 text-sm text-amber-300">
            Email verification is still pending.{" "}
            <Link
              href={`/verify-email?email=${encodeURIComponent(email.trim())}`}
              className="font-medium text-foreground"
            >
              Resend the verification link
            </Link>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="email" className="app-label">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="app-input"
              placeholder="you@example.com"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="app-label">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="app-input"
              placeholder="••••••••"
            />
          </div>

          <div className="flex justify-end">
            <Link href="/forgot-password" className="text-sm text-muted-foreground hover:text-foreground">
              Forgot password?
            </Link>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="app-button-primary w-full disabled:translate-y-0 disabled:opacity-50"
          >
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    }>
      <LoginForm />
    </Suspense>
  );
}
