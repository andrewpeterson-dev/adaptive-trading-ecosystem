/**
 * useOptionsGuard
 *
 * Wraps any apiFetch call. If the response contains code=OPTIONS_NOT_SUPPORTED,
 * sets a flag that triggers the OptionsFallbackModal.
 */
"use client";
import { useState, useCallback } from "react";

export interface OptionsNotSupportedPayload {
  code: "OPTIONS_NOT_SUPPORTED";
  active_broker: string;
  available_options_providers: Array<{
    id: number;
    name: string;
    slug: string;
    is_connected: boolean;
  }>;
}

export function useOptionsGuard() {
  const [payload, setPayload] = useState<OptionsNotSupportedPayload | null>(null);

  const guard = useCallback((error: unknown) => {
    if (
      error &&
      typeof error === "object" &&
      "code" in error &&
      (error as any).code === "OPTIONS_NOT_SUPPORTED"
    ) {
      setPayload(error as OptionsNotSupportedPayload);
      return true;
    }
    return false;
  }, []);

  const dismiss = useCallback(() => setPayload(null), []);

  return { payload, guard, dismiss };
}
