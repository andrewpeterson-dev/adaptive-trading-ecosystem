"use client";

import React, { useState } from "react";
import { RotateCcw, Loader2, Activity } from "lucide-react";
import type { ModelDetail } from "@/types/models";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const TYPE_COLORS: Record<string, string> = {
  MomentumModel: "border-blue-500/25 bg-blue-500/12 text-blue-200",
  MeanReversionModel: "border-amber-500/25 bg-amber-500/12 text-amber-200",
  MLModel: "border-violet-500/25 bg-violet-500/12 text-violet-200",
  BreakoutModel: "border-cyan-500/25 bg-cyan-500/12 text-cyan-200",
  StatArbModel: "border-pink-500/25 bg-pink-500/12 text-pink-200",
};

function metricColor(
  value: number,
  goodThreshold: number,
  badThreshold: number,
  invert = false
): string {
  if (invert) {
    if (value <= goodThreshold) return "text-emerald-400";
    if (value >= badThreshold) return "text-red-400";
    return "text-amber-400";
  }
  if (value >= goodThreshold) return "text-emerald-400";
  if (value <= badThreshold) return "text-red-400";
  return "text-amber-400";
}

export function ModelCard({
  model,
  onRetrain,
  retrainAvailable = false,
}: {
  model: ModelDetail;
  onRetrain: (name: string) => void;
  retrainAvailable?: boolean;
}) {
  const [retraining, setRetraining] = useState(false);
  const typeClass =
    TYPE_COLORS[model.model_type] || "border-border/75 bg-muted/50 text-muted-foreground";

  const handleRetrain = async () => {
    if (!retrainAvailable) return;
    setRetraining(true);
    try {
      await onRetrain(model.name);
    } finally {
      setRetraining(false);
    }
  };

  const sharpe = model.sharpe_ratio ?? 0;
  const sortino = model.sortino_ratio ?? 0;
  const winRate = model.win_rate ?? 0;
  const maxDrawdown = model.max_drawdown ?? 0;
  const totalReturn = model.total_return ?? 0;

  return (
    <div className="app-panel p-5">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                model.is_active
                  ? "bg-emerald-400 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]"
                  : "bg-muted-foreground/40"
              }`}
            />
            <div>
              <h3 className="text-sm font-semibold text-foreground">{model.name}</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {model.is_active ? "Active in production" : "Inactive model"}
              </p>
            </div>
          </div>
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${typeClass}`}
          >
            {model.model_type.replace("Model", "")}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-[20px] border border-border/65 bg-muted/30 p-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Sharpe
            </div>
            <div
              className={`text-sm font-mono font-medium tabular-nums ${metricColor(
                sharpe,
                1.0,
                0.0
              )}`}
            >
              {model.sharpe_ratio != null ? sharpe.toFixed(3) : "—"}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Sortino
            </div>
            <div
              className={`text-sm font-mono font-medium tabular-nums ${metricColor(
                sortino,
                1.5,
                0.0
              )}`}
            >
              {model.sortino_ratio != null ? sortino.toFixed(3) : "—"}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Win Rate
            </div>
            <div
              className={`text-sm font-mono font-medium tabular-nums ${metricColor(
                winRate,
                0.55,
                0.4
              )}`}
            >
              {model.win_rate != null ? `${(winRate * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Max DD
            </div>
            <div
              className={`text-sm font-mono font-medium tabular-nums ${metricColor(
                maxDrawdown,
                0.05,
                0.15,
                true
              )}`}
            >
              {model.max_drawdown != null ? `${(maxDrawdown * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Return
            </div>
            <div
              className={`text-sm font-mono font-medium tabular-nums ${metricColor(
                totalReturn,
                0.05,
                -0.02
              )}`}
            >
              {model.total_return != null ? `${(totalReturn * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Trades
            </div>
            <div className="text-sm font-mono tabular-nums text-muted-foreground">
              {model.num_trades}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3">
          <Badge variant={model.is_active ? "positive" : "neutral"}>
            <Activity className="h-3.5 w-3.5" />
            {model.is_active ? "Enabled" : "Disabled"}
          </Badge>
          <Button
            onClick={handleRetrain}
            disabled={!retrainAvailable || retraining}
            title={retrainAvailable ? undefined : "Retrain not available"}
            variant="secondary"
            size="sm"
            className="h-9 px-4 text-xs"
          >
            {retraining ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RotateCcw className="h-3 w-3" />
            )}
            {retraining ? "Retraining..." : retrainAvailable ? "Retrain" : "Retrain unavailable"}
          </Button>
        </div>
      </div>
    </div>
  );
}
