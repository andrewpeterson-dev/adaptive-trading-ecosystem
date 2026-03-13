"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Loader2, Mail } from "lucide-react";
import { AuthShell } from "@/components/layout/AuthShell";
import { requestPasswordReset } from "@/lib/api/auth";
import { stashResetPreviewUrl } from "@/lib/auth-preview";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const response = await requestPasswordReset(email);
      setMessage(response.message);
      setPreviewUrl(response.development_reset_url || null);
      stashResetPreviewUrl(response.development_reset_url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not send reset instructions.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Reset your password"
      description="We’ll email a time-limited reset link so you can get back into your account safely."
      footer={
        <>
          Remembered it?{" "}
          <Link href="/login" className="font-medium text-foreground">
            Sign in
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
        {message && (
          <div className="rounded-[22px] border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-foreground">
            <div className="flex items-start gap-3">
              <Mail className="mt-0.5 h-4 w-4 text-sky-400" />
              <div className="space-y-2">
                <p>{message}</p>
                {previewUrl && (
                  <a
                    href={previewUrl}
                    className="inline-flex text-sm font-medium underline decoration-white/30 underline-offset-4"
                  >
                    Open development reset link
                  </a>
                )}
              </div>
            </div>
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

          <button
            type="submit"
            disabled={submitting}
            className="app-button-primary w-full disabled:translate-y-0 disabled:opacity-50"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? "Sending reset link…" : "Send reset link"}
          </button>
        </form>
      </div>
    </AuthShell>
  );
}
