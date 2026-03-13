"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { AuthShell } from "@/components/layout/AuthShell";
import { consumeResetPreviewUrl } from "@/lib/auth-preview";
import { confirmPasswordReset } from "@/lib/api/auth";
import {
  getPasswordPolicyError,
  PASSWORD_POLICY_MESSAGE,
} from "@/lib/password-policy";

function ResetPasswordContent() {
  const params = useSearchParams();
  const token = params.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    setPreviewUrl(consumeResetPreviewUrl());
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!token) {
      setError("Reset link is missing or invalid.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    const passwordError = getPasswordPolicyError(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    setSubmitting(true);
    try {
      const response = await confirmPasswordReset(token, password);
      setMessage(response.message || "Password updated. Sign in with your new password.");
      setPassword("");
      setConfirmPassword("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not reset password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Choose a new password"
      description="Reset links expire quickly. Set a new password, then sign in again."
      footer={
        <>
          Need another link?{" "}
          <Link href="/forgot-password" className="font-medium text-foreground">
            Request a new reset email
          </Link>
        </>
      }
    >
      <div className="space-y-5">
        {!token && previewUrl && (
          <div className="rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-foreground">
            <a
              href={previewUrl}
              className="font-medium underline decoration-white/30 underline-offset-4"
            >
              Open development reset link
            </a>
          </div>
        )}
        {error && (
          <div className="rounded-[22px] border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}
        {message && (
          <div className="rounded-[22px] border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-300">
            {message}{" "}
            <Link href="/login" className="font-medium text-foreground">
              Sign in
            </Link>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="password" className="app-label">
              New password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="app-input"
              placeholder="Create a strong password"
            />
            <p className="text-xs text-muted-foreground">
              {PASSWORD_POLICY_MESSAGE}
            </p>
          </div>

          <div className="space-y-2">
            <label htmlFor="confirmPassword" className="app-label">
              Confirm new password
            </label>
            <input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="app-input"
              placeholder="Repeat password"
            />
          </div>

          <button
            type="submit"
            disabled={submitting || !token}
            className="app-button-primary w-full disabled:translate-y-0 disabled:opacity-50"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? "Updating password…" : "Update password"}
          </button>
        </form>
      </div>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <ResetPasswordContent />
    </Suspense>
  );
}
