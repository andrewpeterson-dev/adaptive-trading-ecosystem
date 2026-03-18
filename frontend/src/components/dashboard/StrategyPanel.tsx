"use client";

import React from "react";
import { Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import { EmptyState } from "@/components/ui/empty-state";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StrategyItem {
  id: string;
  name: string;
  status: "active" | "paused" | "backtesting";
  mode: "paper" | "live";
  winRate?: number; // 0-100
  trades?: number;
  pnl?: number;
}

interface StrategyPanelProps {
  strategies?: StrategyItem[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_STRATEGIES = 5;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}${value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  StrategyItem["status"],
  { label: string; className: string }
> = {
  active: {
    label: "Active",
    className: "text-emerald-400 bg-emerald-400/10 border-emerald-500/25",
  },
  paused: {
    label: "Paused",
    className: "text-amber-400 bg-amber-400/10 border-amber-500/25",
  },
  backtesting: {
    label: "Backtesting",
    className: "text-sky-400 bg-sky-400/10 border-sky-500/25",
  },
};

function StatusBadge({ status }: { status: StrategyItem["status"] }) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]",
        config.className
      )}
    >
      {status === "active" && (
        <span className="mr-1 h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse-dot" />
      )}
      {config.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Mode badge
// ---------------------------------------------------------------------------

function ModeBadge({ mode }: { mode: "paper" | "live" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]",
        mode === "live"
          ? "text-amber-300 bg-amber-500/10"
          : "text-muted-foreground bg-muted/50"
      )}
    >
      {mode}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Strategy card
// ---------------------------------------------------------------------------

function StrategyCard({ strategy }: { strategy: StrategyItem }) {
  const pnlColor =
    strategy.pnl != null
      ? strategy.pnl >= 0
        ? "text-emerald-400"
        : "text-red-400"
      : "text-muted-foreground";

  const winRateColor =
    strategy.winRate != null
      ? strategy.winRate >= 50
        ? "bg-emerald-500"
        : "bg-red-500"
      : "bg-primary";

  return (
    <div className="app-inset p-3 space-y-2.5">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <span className="text-sm font-semibold text-foreground truncate">
          {strategy.name}
        </span>
        <div className="flex items-center gap-1.5 shrink-0">
          <ModeBadge mode={strategy.mode} />
          <StatusBadge status={strategy.status} />
        </div>
      </div>

      {/* Win rate bar */}
      {strategy.winRate != null && (
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-muted-foreground uppercase tracking-wider font-medium">
              Win Rate
            </span>
            <span className="font-mono tabular-nums text-foreground">
              {strategy.winRate.toFixed(1)}%
            </span>
          </div>
          <Progress
            value={strategy.winRate}
            className="h-1.5"
            indicatorClassName={winRateColor}
          />
        </div>
      )}

      {/* Footer stats */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">
          {strategy.trades != null ? (
            <span className="font-mono tabular-nums">{strategy.trades}</span>
          ) : (
            "0"
          )}{" "}
          trades
        </span>
        {strategy.pnl != null && (
          <span className={cn("font-mono tabular-nums font-medium", pnlColor)}>
            {formatCurrency(strategy.pnl)}
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function StrategyPanel({ strategies }: StrategyPanelProps) {
  const displayStrategies = (strategies ?? []).slice(0, MAX_STRATEGIES);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Zap className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">Strategies</h3>
        {displayStrategies.length > 0 && (
          <span className="rounded-full bg-muted/50 px-2 py-1 text-[10px] font-mono text-muted-foreground">
            {displayStrategies.length}
          </span>
        )}
      </div>

      {displayStrategies.length === 0 ? (
        <div className="app-inset">
          <EmptyState
            className="py-8"
            icon={
              <span className="animate-pulse" style={{ animationDuration: '3s' }}>
                <Zap className="h-4 w-4 text-muted-foreground" />
              </span>
            }
            title="No active strategies"
            description="Cerberus monitoring setup conditions"
          />
        </div>
      ) : (
        <div className="space-y-2">
          {displayStrategies.map((s) => (
            <StrategyCard key={s.id} strategy={s} />
          ))}
        </div>
      )}
    </div>
  );
}

export type { StrategyItem, StrategyPanelProps };
