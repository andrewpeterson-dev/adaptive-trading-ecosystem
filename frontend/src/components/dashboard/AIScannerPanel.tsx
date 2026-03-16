"use client";

import {
  Search,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScannerSignal {
  symbol: string;
  signal: string;
  confidence: number; // 0-100
  direction?: "long" | "short";
}

interface AIScannerPanelProps {
  totalWatching?: number;
  signals?: ScannerSignal[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MAX_VISIBLE = 5;

function confidenceBadgeClasses(value: number): string {
  if (value >= 70) return "bg-[#10b981]/10 text-[#10b981] border-[#10b981]/20";
  if (value >= 50) return "bg-[#f59e0b]/10 text-[#f59e0b] border-[#f59e0b]/20";
  return "bg-[#ef4444]/10 text-[#ef4444] border-[#ef4444]/20";
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function AIScannerPanel({
  totalWatching = 0,
  signals = [],
}: AIScannerPanelProps) {
  const visible = signals.slice(0, MAX_VISIBLE);
  const remaining = signals.length - MAX_VISIBLE;

  return (
    <section className="app-panel p-5 sm:p-6">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Search className="h-4 w-4 text-sky-400" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            AI Scanner
          </span>
        </div>
        {totalWatching > 0 && (
          <span className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold tabular-nums text-muted-foreground"
            style={{ borderColor: "hsl(var(--border) / 0.75)" }}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse-dot" />
            Watching: {totalWatching.toLocaleString()} symbols
          </span>
        )}
      </div>

      {/* ── Strong Signals ─────────────────────────────────────────────── */}
      {visible.length === 0 ? (
        <div className="app-inset px-5 py-10 text-center">
          <TrendingUp className="mx-auto h-8 w-8 text-muted-foreground/40 mb-3" />
          <p className="text-sm text-muted-foreground max-w-xs mx-auto leading-6">
            No strong signals detected. The scanner will surface opportunities as
            they emerge.
          </p>
        </div>
      ) : (
        <>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-3">
            Strong Signals
          </div>
          <div className="space-y-2">
            {visible.map((s) => {
              const DirectionIcon =
                s.direction === "short" ? ArrowDownRight : ArrowUpRight;
              const dirColor =
                s.direction === "short"
                  ? "text-[#ef4444]"
                  : "text-[#10b981]";

              return (
                <div
                  key={`${s.symbol}-${s.signal}`}
                  className="app-inset flex items-center gap-3 px-3.5 py-3"
                >
                  {/* Direction arrow */}
                  <DirectionIcon
                    className={cn("h-4 w-4 shrink-0", dirColor)}
                  />

                  {/* Symbol + signal description */}
                  <div className="flex-1 min-w-0">
                    <span className="font-mono text-sm font-bold text-foreground">
                      {s.symbol}
                    </span>
                    <p className="text-xs text-muted-foreground truncate mt-0.5">
                      {s.signal}
                    </p>
                  </div>

                  {/* Confidence badge */}
                  <span
                    className={cn(
                      "shrink-0 inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold tabular-nums",
                      confidenceBadgeClasses(s.confidence),
                    )}
                  >
                    {s.confidence}%
                  </span>
                </div>
              );
            })}
          </div>

          {/* ── View all link ────────────────────────────────────────────── */}
          {remaining > 0 && (
            <button
              type="button"
              className="mt-3 w-full text-center text-xs font-medium text-sky-400 hover:text-sky-300 transition-colors py-1.5"
            >
              View all {signals.length} signals
            </button>
          )}
        </>
      )}
    </section>
  );
}

export type { ScannerSignal, AIScannerPanelProps };
