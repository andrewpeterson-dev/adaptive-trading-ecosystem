"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";

interface LedgerData {
  broker_equity: number;
  broker_label: string;
  options_sim_pnl: number;
  options_label: string;
  total_simulated_equity: number;
  metrics: {
    returns_pct: number;
    drawdown_pct: number;
    sharpe: number;
  };
}

function fmt(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

export function CombinedLedgerCard() {
  const [data, setData] = useState<LedgerData | null>(null);

  useEffect(() => {
    apiFetch<LedgerData>("/api/v2/ledger/combined")
      .then(setData)
      .catch(() => null);
  }, []);

  // Self-hide when no options fallback active
  if (!data || data.options_sim_pnl === 0) return null;

  const pnlColor = data.options_sim_pnl >= 0 ? "text-emerald-400" : "text-red-400";

  return (
    <div className="app-panel p-5">
      <div className="space-y-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        Combined Simulated Equity
      </p>
      <div className="flex items-end justify-between">
        <span className="text-2xl font-mono font-semibold text-foreground">
          {fmt(data.total_simulated_equity)}
        </span>
        <span
          className={`text-sm font-mono ${
            data.metrics.returns_pct >= 0 ? "text-emerald-300" : "text-red-300"
          }`}
        >
          {data.metrics.returns_pct >= 0 ? "+" : ""}{data.metrics.returns_pct.toFixed(2)}%
        </span>
      </div>
      <div className="space-y-2 rounded-[18px] border border-border/70 bg-muted/30 p-4 text-sm">
        <div className="flex justify-between text-muted-foreground">
          <span>{data.broker_label}</span>
          <span className="font-mono text-foreground">{fmt(data.broker_equity)}</span>
        </div>
        <div className="flex justify-between text-muted-foreground">
          <span>{data.options_label}</span>
          <span className={`font-mono ${pnlColor}`}>
            {data.options_sim_pnl >= 0 ? "+" : ""}{fmt(data.options_sim_pnl)}
          </span>
        </div>
        <div className="flex justify-between border-t border-border pt-1 font-medium">
          <span>Total</span>
          <span className="font-mono">{fmt(data.total_simulated_equity)}</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <div>
          Drawdown{" "}
          <span className="font-mono text-foreground">
            {data.metrics.drawdown_pct.toFixed(2)}%
          </span>
        </div>
        <div>
          Sharpe{" "}
          <span className="font-mono text-foreground">
            {data.metrics.sharpe.toFixed(2)}
          </span>
        </div>
      </div>
      </div>
    </div>
  );
}
