"use client";

import React, { useState } from "react";
import { RotateCcw, Loader2 } from "lucide-react";
import type { ModelDetail } from "@/types/models";

const TYPE_COLORS: Record<string, string> = {
  MomentumModel: "text-blue-400 bg-blue-400/10 border-blue-400/30",
  MeanReversionModel: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  MLModel: "text-purple-400 bg-purple-400/10 border-purple-400/30",
  BreakoutModel: "text-cyan-400 bg-cyan-400/10 border-cyan-400/30",
  StatArbModel: "text-pink-400 bg-pink-400/10 border-pink-400/30",
};

function metricColor(value: number, goodThreshold: number, badThreshold: number, invert = false): string {
  if (invert) {
    if (value <= goodThreshold) return "text-emerald-400";
    if (value >= badThreshold) return "text-red-400";
    return "text-amber-400";
  }
  if (value >= goodThreshold) return "text-emerald-400";
  if (value <= badThreshold) return "text-red-400";
  return "text-amber-400";
}

export function ModelCard({ model, onRetrain }: { model: ModelDetail; onRetrain: (name: string) => void }) {
  const [retraining, setRetraining] = useState(false);
  const m = model.metrics;
  const typeClass = TYPE_COLORS[model.type] || "text-muted-foreground bg-muted border-border";

  const handleRetrain = async () => {
    setRetraining(true);
    try {
      await onRetrain(model.name);
    } finally {
      setRetraining(false);
    }
  };

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2 w-2 rounded-full ${model.is_trained ? "bg-emerald-400" : "bg-muted-foreground/40"}`} />
          <h3 className="text-sm font-semibold">{model.name}</h3>
        </div>
        <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${typeClass}`}>
          {model.type.replace("Model", "")}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Sharpe</div>
          <div className={`text-sm font-mono font-medium ${metricColor(m.sharpe_ratio, 1.0, 0.0)}`}>
            {m.sharpe_ratio.toFixed(3)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Sortino</div>
          <div className={`text-sm font-mono font-medium ${metricColor(m.sortino_ratio, 1.5, 0.0)}`}>
            {m.sortino_ratio.toFixed(3)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Win Rate</div>
          <div className={`text-sm font-mono font-medium ${metricColor(m.win_rate, 0.55, 0.4)}`}>
            {(m.win_rate * 100).toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Max DD</div>
          <div className={`text-sm font-mono font-medium ${metricColor(m.max_drawdown, 0.05, 0.15, true)}`}>
            {(m.max_drawdown * 100).toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Return</div>
          <div className={`text-sm font-mono font-medium ${metricColor(m.total_return, 0.05, -0.02)}`}>
            {(m.total_return * 100).toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Trades</div>
          <div className="text-sm font-mono text-muted-foreground">{m.num_trades}</div>
        </div>
      </div>

      <button
        onClick={handleRetrain}
        disabled={retraining}
        className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md border text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
      >
        {retraining ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <RotateCcw className="h-3 w-3" />
        )}
        {retraining ? "Retraining..." : "Retrain"}
      </button>
    </div>
  );
}
