"use client";

import { BrainCircuit, Gauge, ShieldAlert } from "lucide-react";

import type { BotDetail, BotTrade } from "@/lib/cerberus-api";
import {
  formatProbability,
  getAiOverview,
  getBotConfig,
  humanizeLabel,
  summarizeRisk,
} from "@/lib/bot-visualization";

interface AIExplanationPanelProps {
  detail: BotDetail;
  trade: BotTrade | null;
}

export function AIExplanationPanel({
  detail,
  trade,
}: AIExplanationPanelProps) {
  const config = getBotConfig(detail);
  const aiContext = (config.ai_context ?? {}) as Record<string, unknown>;
  const indicators =
    trade?.indicatorSignals?.length
      ? trade.indicatorSignals
      : detail.learningStatus.featureSignals.length > 0
        ? detail.learningStatus.featureSignals
        : Array.isArray(config.feature_signals)
          ? (config.feature_signals as string[])
          : [];

  const assumptions = Array.isArray(aiContext.assumptions)
    ? aiContext.assumptions.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];

  const reasoning =
    trade?.botExplanation ||
    trade?.reasons?.join("; ") ||
    getAiOverview(detail);

  return (
    <section className="app-panel p-5 sm:p-6">
      <div className="mb-5 flex items-center gap-2">
        <BrainCircuit className="h-4 w-4 text-sky-400" />
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            AI Decision Insights
          </div>
          <h3 className="mt-1 text-lg font-semibold text-foreground">Trade trigger explanation</h3>
        </div>
      </div>

      <div className="rounded-[22px] border border-border/60 bg-muted/10 p-4">
        <div className="text-sm leading-7 text-foreground">{reasoning}</div>
        {trade?.reasons && trade.reasons.length > 0 && (
          <div className="mt-4 grid gap-2">
            {trade.reasons.map((reason) => (
              <div
                key={reason}
                className="rounded-2xl border border-border/60 bg-background/70 px-3 py-2 text-xs text-muted-foreground"
              >
                {reason}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <div className="rounded-[20px] border border-border/60 bg-muted/10 px-4 py-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            <Gauge className="h-3.5 w-3.5 text-fuchsia-400" />
            Probability Score
          </div>
          <div className="mt-3 text-lg font-semibold text-foreground">
            {formatProbability(trade?.probabilityScore ?? null)}
          </div>
          <div className="mt-2 text-xs text-muted-foreground">
            {trade?.probabilityScore == null ? "No explicit score was captured for this execution." : "Execution-time confidence stored with the trade."}
          </div>
        </div>

        <div className="rounded-[20px] border border-border/60 bg-muted/10 px-4 py-4">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
            Risk Assessment
          </div>
          <div className="mt-3 text-lg font-semibold text-foreground">
            {trade?.riskAssessment || summarizeRisk(config)}
          </div>
          <div className="mt-2 text-xs text-muted-foreground">
            Based on sizing, stop placement, and exposure settings.
          </div>
        </div>

        <div className="rounded-[20px] border border-border/60 bg-muted/10 px-4 py-4">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Active Trade
          </div>
          <div className="mt-3 text-lg font-semibold text-foreground">
            {trade ? `${trade.symbol} ${trade.side.toUpperCase()}` : "No trade selected"}
          </div>
          <div className="mt-2 text-xs text-muted-foreground">
            Select a chart marker or table row to inspect trade-specific context.
          </div>
        </div>
      </div>

      <div className="mt-5">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Indicators Used
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {indicators.length > 0 ? (
            indicators.map((indicator) => (
              <span
                key={indicator}
                className="rounded-full border border-sky-400/20 bg-sky-400/5 px-2.5 py-1 text-[11px] font-medium text-sky-400"
              >
                {humanizeLabel(indicator)}
              </span>
            ))
          ) : (
            <span className="text-sm text-muted-foreground">No indicator metadata captured.</span>
          )}
        </div>
      </div>

      {assumptions.length > 0 && (
        <div className="mt-5">
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Model Assumptions
          </div>
          <div className="mt-3 space-y-2">
            {assumptions.map((assumption) => (
              <div
                key={assumption}
                className="rounded-2xl border border-border/60 bg-background/70 px-3 py-2 text-xs text-muted-foreground"
              >
                {assumption}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
