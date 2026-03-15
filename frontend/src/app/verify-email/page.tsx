"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle, Loader2, Mail, RefreshCw, XCircle } from "lucide-react";
import { AuthShell } from "@/components/layout/AuthShell";
import { consumeVerificationPreviewUrl } from "@/lib/auth-preview";
import { resendVerification, verifyEmail } from "@/lib/api/auth";

type VerificationState = "idle" | "verifying" | "verified" | "resent" | "error";

function VerifyEmailContent() {
  const params = useSearchParams();
  const token = params?.get("token") ?? null;
  const initialEmail = params?.get("email") || "";

  const [email, setEmail] = useState(initialEmail);
  const [state, setState] = useState<VerificationState>(token ? "verifying" : "idle");
  const [message, setMessage] = useState(
    token ? "Verifying your email address..." : "Check your inbox for a verification link."
  );
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setPreviewUrl(consumeVerificationPreviewUrl());
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }

    let cancelled = false;
    setState("verifying");
    setMessage("Verifying your email address...");

    verifyEmail(token)
      .then((result) => {
        if (cancelled) {
          return;
        }
        setState("verified");
        setMessage(result.message || "Email verified. You can sign in now.");
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        setState("error");
        setMessage(error instanceof Error ? error.message : "Verification failed.");
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handleResend(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const response = await resendVerification(email);
      setPreviewUrl(response.development_verification_url || null);
      setState("resent");
      setMessage(response.message || "If that email still needs verification, a fresh link was sent.");
    } catch (error: unknown) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Could not resend verification email.");
    } finally {
      setSubmitting(false);
    }
  }

  const isVerified = state === "verified";
  const isError = state === "error";
  const isVerifying = state === "verifying";

  return (
    <AuthShell
      title={isVerified ? "Email verified" : "Verify your email"}
      description={
        isVerified
          ? "Your account is active. Sign in to continue onboarding."
          : "Finish account setup before you sign in or connect a broker."
      }
      footer={
        <>
          Already verified?{" "}
          <Link href="/login" className="font-medium text-foreground">
            Sign in
          </Link>
        </>
      }
    >
      <div className="space-y-5">
        <div className="rounded-[22px] border border-white/10 bg-white/[0.03] px-5 py-4">
          <div className="flex items-start gap-3">
            {isVerified ? (
              <CheckCircle className="mt-0.5 h-5 w-5 text-emerald-400" />
            ) : isError ? (
              <XCircle className="mt-0.5 h-5 w-5 text-red-400" />
            ) : isVerifying ? (
              <Loader2 className="mt-0.5 h-5 w-5 animate-spin text-sky-400" />
            ) : (
              <Mail className="mt-0.5 h-5 w-5 text-sky-400" />
            )}
            <div className="space-y-2">
              <p className="text-sm text-foreground">{message}</p>
              {!token && email && (
                <p className="text-xs text-muted-foreground">
                  Expected inbox: <span className="text-foreground">{email}</span>
                </p>
              )}
              {previewUrl && (
                <a
                  href={previewUrl}
                  className="inline-flex text-sm font-medium text-foreground underline decoration-white/30 underline-offset-4"
                >
                  Open development preview link
                </a>
              )}
            </div>
          </div>
        </div>

        {!isVerified && (
          <form onSubmit={handleResend} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="email" className="app-label">
                Resend verification email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
                className="app-input"
                placeholder="you@example.com"
              />
            </div>

            <button
              type="submit"
              disabled={submitting || !email.trim()}
              className="app-button-primary w-full disabled:translate-y-0 disabled:opacity-50"
            >
              {submitting && <RefreshCw className="h-4 w-4 animate-spin" />}
              {submitting ? "Sending link…" : "Resend verification link"}
            </button>
          </form>
        )}
      </div>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
