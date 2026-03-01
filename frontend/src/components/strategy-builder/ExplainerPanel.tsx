"use client";

import React from "react";
import {
  Brain,
  TrendingUp,
  AlertTriangle,
  Shield,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import type { StrategyExplanation } from "@/types/strategy";

interface ExplainerPanelProps {
  explanation: StrategyExplanation | null;
  loading?: boolean;
}

export function ExplainerPanel({ explanation, loading }: ExplainerPanelProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-border/50 p-6 flex items-center justify-center">
        <div className="animate-pulse flex items-center gap-2 text-muted-foreground">
          <Brain className="h-4 w-4" />
          <span className="text-sm">Analyzing strategy...</span>
        </div>
      </div>
    );
  }

  if (!explanation) {
    return (
      <div className="rounded-lg border border-dashed border-border/50 p-6 flex items-center justify-center">
        <p className="text-sm text-muted-foreground">
          Build a strategy to see AI analysis
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/50 bg-card space-y-0 divide-y divide-border/50">
      {/* Summary */}
      <div className="p-4">
        <div className="flex items-center gap-2 mb-2">
          <Brain className="h-4 w-4 text-primary" />
          <h3 className="font-semibold text-sm">Strategy Analysis</h3>
        </div>
        <p className="text-sm leading-relaxed text-foreground/90">
          {explanation.summary}
        </p>
      </div>

      {/* Market Regime */}
      <div className="p-4">
        <div className="flex items-center gap-2 mb-1">
          <TrendingUp className="h-4 w-4 text-emerald-400" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Target Regime
          </h4>
        </div>
        <p className="text-sm text-foreground/90">{explanation.market_regime}</p>
      </div>

      {/* Strengths & Weaknesses */}
      <div className="grid grid-cols-2 divide-x">
        <div className="p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400 mb-2">
            Strengths
          </h4>
          <ul className="space-y-1.5">
            {explanation.strengths.map((s, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs leading-relaxed">
                <CheckCircle2 className="h-3 w-3 mt-0.5 shrink-0 text-emerald-400/60" />
                <span className="text-foreground/80">{s}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="p-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-red-400 mb-2">
            Weaknesses
          </h4>
          <ul className="space-y-1.5">
            {explanation.weaknesses.map((w, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs leading-relaxed">
                <XCircle className="h-3 w-3 mt-0.5 shrink-0 text-red-400/60" />
                <span className="text-foreground/80">{w}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Risk Profile */}
      <div className="p-4">
        <div className="flex items-center gap-2 mb-1">
          <Shield className="h-4 w-4 text-amber-400" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Risk Profile
          </h4>
        </div>
        <p className="text-sm text-foreground/90">{explanation.risk_profile}</p>
      </div>

      {/* Overfitting Warning */}
      {explanation.overfitting_warning && (
        <div className="p-4 bg-amber-400/5">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 mt-0.5 text-amber-400" />
            <div>
              <h4 className="text-sm font-semibold text-amber-400">
                Overfitting Risk
              </h4>
              <p className="text-xs text-muted-foreground mt-0.5">
                Parameter values or condition count suggest this strategy may be
                over-optimized to historical data. Consider simplifying or using
                walk-forward validation.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
