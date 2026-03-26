"use client";

import { useTradingMode } from "@/hooks/useTradingMode";
import { AlertTriangle } from "lucide-react";

export function PaperModeBanner() {
  const { mode } = useTradingMode();

  if (mode !== "paper") return null;

  return (
    <div className="flex items-center gap-2 rounded-lg border border-amber-800/40 bg-amber-950/20 px-4 py-2.5 text-sm text-amber-300">
      <AlertTriangle className="h-4 w-4 flex-shrink-0" />
      <span>
        <strong>Paper Trading</strong> — Trades are simulated. No real money is at risk.
      </span>
    </div>
  );
}
