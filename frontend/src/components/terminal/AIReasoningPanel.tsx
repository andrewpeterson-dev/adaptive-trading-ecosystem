"use client";

import { BrainCircuit, CheckCircle2, XCircle, AlertTriangle, Clock, Zap, Shield } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import type { BotDetail, BotTrade } from "@/lib/cerberus-api";
import {
  formatProbability,
  getAiOverview,
  getBotConfig,
  humanizeLabel,
  summarizeRisk,
  formatDateTime,
  formatTimeframe,
} from "@/lib/bot-visualization";

interface AIDecisionPanelProps {
  detail: BotDetail;
  trade: BotTrade | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface ValidationCheck {
  label: string;
  status: "confirmed" | "caution" | "risk";
}

function parseValidationChecks(trade: BotTrade | null, detail: BotDetail): ValidationCheck[] {
  const checks: ValidationCheck[] = [];

  // Parse from reasons array -- look for pass/fail/caution patterns
  const reasons = trade?.reasons ?? [];
  for (const reason of reasons) {
    const lower = reason.toLowerCase();
    if (
      lower.includes("above") ||
      lower.includes("passed") ||
      lower.includes("confirmed") ||
      lower.includes("bullish") ||
      lower.includes("increasing") ||
      lower.includes("met") ||
      lower.includes("strong") ||
      lower.includes("positive")
    ) {
      checks.push({ label: reason, status: "confirmed" });
    } else if (
      lower.includes("caution") ||
      lower.includes("elevated") ||
      lower.includes("warning") ||
      lower.includes("moderate") ||
      lower.includes("mixed") ||
      lower.includes("neutral")
    ) {
      checks.push({ label: reason, status: "caution" });
    } else if (
      lower.includes("below") ||
      lower.includes("failed") ||
      lower.includes("bearish") ||
      lower.includes("high risk") ||
      lower.includes("at risk") ||
      lower.includes("declining") ||
      lower.includes("weak") ||
      lower.includes("negative") ||
      lower.includes("violated")
    ) {
      checks.push({ label: reason, status: "risk" });
    } else {
      // Default to confirmed for neutral statements
      checks.push({ label: reason, status: "confirmed" });
    }
  }

  // If no reasons on trade, synthesize from risk assessment
  if (checks.length === 0 && trade?.riskAssessment) {
    const risk = trade.riskAssessment.toLowerCase();
    if (risk.includes("low") || risk.includes("conservative")) {
      checks.push({ label: "Risk assessment: Low", status: "confirmed" });
    } else if (risk.includes("moderate") || risk.includes("balanced")) {
      checks.push({ label: "Risk assessment: Moderate", status: "caution" });
    } else {
      checks.push({ label: `Risk assessment: ${trade.riskAssessment}`, status: "risk" });
    }
  }

  return checks;
}

function extractSignalTrigger(trade: BotTrade | null, detail: BotDetail): string {
  // Try indicator signals first
  if (trade?.indicatorSignals?.length) {
    return trade.indicatorSignals.map(humanizeLabel).join(", ");
  }

  // Try feature signals from learning status
  if (detail.learningStatus.featureSignals.length > 0) {
    return detail.learningStatus.featureSignals.map(humanizeLabel).join(", ");
  }

  // Try config feature signals
  const config = getBotConfig(detail);
  if (Array.isArray(config.feature_signals) && config.feature_signals.length > 0) {
    return (config.feature_signals as string[]).map(humanizeLabel).join(", ");
  }

  return "No signal data captured";
}

function getConfidenceColor(score: number | null | undefined): {
  text: string;
  bg: string;
  bar: string;
} {
  if (score == null) return { text: "text-muted-foreground", bg: "bg-muted/20", bar: "bg-muted-foreground/30" };
  const pct = score * 100;
  if (pct >= 70) return { text: "text-emerald-400", bg: "bg-emerald-400/10", bar: "bg-emerald-400" };
  if (pct >= 50) return { text: "text-amber-400", bg: "bg-amber-400/10", bar: "bg-amber-400" };
  return { text: "text-rose-400", bg: "bg-rose-400/10", bar: "bg-rose-400" };
}

function getStatusIcon(status: ValidationCheck["status"]) {
  switch (status) {
    case "confirmed":
      return <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-emerald-400" />;
    case "caution":
      return <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 text-amber-400" />;
    case "risk":
      return <XCircle className="h-3.5 w-3.5 flex-shrink-0 text-rose-400" />;
  }
}

function getStatusTextColor(status: ValidationCheck["status"]) {
  switch (status) {
    case "confirmed":
      return "text-emerald-400/90";
    case "caution":
      return "text-amber-400/90";
    case "risk":
      return "text-rose-400/90";
  }
}

interface TimelineEvent {
  label: string;
  timestamp: string;
  type: "signal" | "entry" | "exit" | "decision";
}

function buildTimeline(trade: BotTrade | null, detail: BotDetail): TimelineEvent[] {
  const events: TimelineEvent[] = [];

  if (!trade) return events;

  // Latest decision timestamp
  if (detail.latestDecision?.created_at) {
    events.push({
      label: `AI Decision: ${detail.latestDecision.decision}`,
      timestamp: detail.latestDecision.created_at,
      type: "decision",
    });
  }

  // Entry event
  const entryTime = trade.entryTs ?? trade.createdAt;
  if (entryTime) {
    events.push({
      label: `${trade.side.toUpperCase()} ${trade.symbol} @ ${trade.entryPrice != null ? `$${trade.entryPrice.toFixed(2)}` : "market"}`,
      timestamp: entryTime,
      type: "entry",
    });
  }

  // Exit event
  if (trade.exitTs && trade.exitPrice != null) {
    events.push({
      label: `Exit ${trade.symbol} @ $${trade.exitPrice.toFixed(2)}`,
      timestamp: trade.exitTs,
      type: "exit",
    });
  }

  // Sort chronologically
  events.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  return events;
}

function getTimelineDotColor(type: TimelineEvent["type"]) {
  switch (type) {
    case "signal":
      return "bg-sky-400";
    case "entry":
      return "bg-emerald-400";
    case "exit":
      return "bg-rose-400";
    case "decision":
      return "bg-fuchsia-400";
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AIReasoningPanel({ detail, trade }: AIDecisionPanelProps) {
  const config = getBotConfig(detail);
  const confidenceScore = trade?.probabilityScore ?? null;
  const confidenceColors = getConfidenceColor(confidenceScore);
  const signalTrigger = extractSignalTrigger(trade, detail);
  const validationChecks = parseValidationChecks(trade, detail);
  const timeline = buildTimeline(trade, detail);
  const riskLabel = trade?.riskAssessment || summarizeRisk(config);
  const timeframe = config.timeframe as string | undefined;
  const reasoning = trade?.botExplanation || getAiOverview(detail);

  // Hold time estimate based on timeframe
  const holdTimeEstimate: Record<string, string> = {
    "1m": "Minutes",
    "5m": "15-60 min",
    "15m": "1-4 hours",
    "1H": "4-24 hours",
    "4H": "1-3 days",
    "1D": "2-10 days",
    "1W": "1-4 weeks",
  };

  if (!trade) {
    return (
      <TerminalPanel
        title="AI Trade Decision"
        icon={<BrainCircuit className="h-3.5 w-3.5" />}
        accent="text-fuchsia-400"
        compact
      >
        <div className="flex h-full items-center justify-center">
          <div className="text-center">
            <BrainCircuit className="mx-auto h-8 w-8 text-muted-foreground/30" />
            <p className="mt-3 text-sm text-muted-foreground">Select a trade to view AI reasoning</p>
            <p className="mt-1 text-xs text-muted-foreground/60">
              Click a chart marker or table row
            </p>
          </div>
        </div>
      </TerminalPanel>
    );
  }

  return (
    <TerminalPanel
      title="AI Trade Decision"
      icon={<BrainCircuit className="h-3.5 w-3.5" />}
      accent="text-fuchsia-400"
      compact
      actions={
        <span className={`rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
          trade.status === "open"
            ? "bg-emerald-400/10 text-emerald-400"
            : "bg-muted/30 text-muted-foreground"
        }`}>
          {trade.status}
        </span>
      }
    >
      <div className="space-y-4">
        {/* Signal Trigger */}
        <div>
          <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            <Zap className="h-3 w-3 text-amber-400" />
            Signal Trigger
          </div>
          <div className="mt-1.5 rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
            <span className="text-xs font-medium text-foreground">{signalTrigger}</span>
          </div>
        </div>

        {/* Validation Checks */}
        {validationChecks.length > 0 && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Validation
            </div>
            <div className="mt-1.5 space-y-1">
              {validationChecks.map((check) => (
                <div
                  key={check.label}
                  className="flex items-start gap-2 rounded-lg px-2 py-1.5 text-xs"
                >
                  {getStatusIcon(check.status)}
                  <span className={getStatusTextColor(check.status)}>
                    {check.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Confidence Score */}
        <div>
          <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            <Shield className="h-3 w-3 text-sky-400" />
            Confidence
          </div>
          <div className="mt-1.5 rounded-xl border border-border/40 bg-muted/10 px-3 py-2.5">
            <div className="flex items-center justify-between">
              <span className={`text-2xl font-bold font-mono tabular-nums ${confidenceColors.text}`}>
                {formatProbability(confidenceScore)}
              </span>
              <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                {riskLabel}
              </span>
            </div>
            {confidenceScore != null && (
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted/30">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${confidenceColors.bar}`}
                  style={{ width: `${Math.min(confidenceScore * 100, 100)}%` }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Hold Time */}
        {timeframe && (
          <div className="flex items-center justify-between rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 text-muted-foreground/60" />
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Hold Time
              </span>
            </div>
            <span className="text-xs font-medium text-foreground">
              {holdTimeEstimate[timeframe] ?? formatTimeframe(timeframe)}
            </span>
          </div>
        )}

        {/* AI Reasoning Summary */}
        {reasoning && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Reasoning
            </div>
            <div className="mt-1.5 rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
              <p className="text-xs leading-5 text-muted-foreground">{reasoning}</p>
            </div>
          </div>
        )}

        {/* Decision Timeline */}
        {timeline.length > 0 && (
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Timeline
            </div>
            <div className="mt-1.5 space-y-0">
              {timeline.map((event, i) => (
                <div key={`${event.type}-${event.timestamp}`} className="flex items-start gap-2.5 py-1.5">
                  <div className="flex flex-col items-center pt-1">
                    <span className={`h-2 w-2 rounded-full ${getTimelineDotColor(event.type)}`} />
                    {i < timeline.length - 1 && (
                      <div className="mt-0.5 h-full w-px bg-border/40" style={{ minHeight: 16 }} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-foreground truncate">{event.label}</div>
                    <div className="text-[10px] text-muted-foreground/70 font-mono tabular-nums">
                      {formatDateTime(event.timestamp)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </TerminalPanel>
  );
}
