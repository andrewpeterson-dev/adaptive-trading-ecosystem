"use client";

import React from "react";
import { useTradeStore } from "@/stores/trade-store";

function formatCurrency(val: number | null | undefined): string {
  if (val == null) return "\u2014";
  return val.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

function SkeletonCard({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-border/50 bg-card p-4">
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
        {label}
      </div>
      <div className="h-6 w-24 animate-pulse bg-muted rounded" />
    </div>
  );
}

export function MetricsBar() {
  const account = useTradeStore((s) => s.account);
  const positions = useTradeStore((s) => s.positions);

  if (!account) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SkeletonCard label="Cash Balance" />
        <SkeletonCard label="Portfolio Value" />
        <SkeletonCard label="Total Equity" />
        <SkeletonCard label="Unrealized P&L" />
      </div>
    );
  }

  const unrealizedPnl = positions.reduce(
    (sum, p) => sum + (p.unrealized_pnl ?? 0),
    0
  );
  const pnlUp = unrealizedPnl >= 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div className="rounded-xl border border-border/50 bg-card p-4">
        <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
          Cash Balance
        </div>
        <div className="text-base font-mono font-bold tabular-nums tracking-tight">
          {formatCurrency(account.cash)}
        </div>
      </div>
      <div className="rounded-xl border border-border/50 bg-card p-4">
        <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
          Portfolio Value
        </div>
        <div className="text-base font-mono font-bold tabular-nums tracking-tight">
          {formatCurrency(account.portfolio_value)}
        </div>
      </div>
      <div className="rounded-xl border border-border/50 bg-card p-4">
        <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
          Total Equity
        </div>
        <div className="text-base font-mono font-bold tabular-nums tracking-tight">
          {formatCurrency(account.equity)}
        </div>
      </div>
      <div className="rounded-xl border border-border/50 bg-card p-4">
        <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
          Unrealized P&L
        </div>
        <div
          className={`text-base font-mono font-bold tabular-nums tracking-tight ${
            pnlUp ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {pnlUp ? "+" : ""}
          {unrealizedPnl.toLocaleString("en-US", {
            style: "currency",
            currency: "USD",
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </div>
      </div>
    </div>
  );
}
