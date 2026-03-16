"use client";

import {
  Brain,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AIDecision {
  signal: { name: string; detail: string };
  checks: Array<{ label: string; status: "pass" | "warn" | "fail" }>;
  confidence: number; // 0-100
  holdTime?: string;
  timeline?: Array<{ time: string; event: string }>;
  timestamp?: string;
}

interface AIReasoningPanelProps {
  decision?: AIDecision | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_ICON = {
  pass: CheckCircle2,
  warn: AlertTriangle,
  fail: XCircle,
} as const;

const STATUS_COLOR = {
  pass: "text-[#10b981]",
  warn: "text-[#f59e0b]",
  fail: "text-[#ef4444]",
} as const;

function confidenceColor(value: number): string {
  if (value >= 70) return "#10b981";
  if (value >= 50) return "#f59e0b";
  return "#ef4444";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ConfidenceRing({ value }: { value: number }) {
  const size = 96;
  const stroke = 7;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  const color = confidenceColor(value);

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg
        className="score-ring"
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
      >
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          className="text-border/40"
          strokeWidth={stroke}
        />
        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 600ms ease" }}
        />
      </svg>
      <span
        className="absolute text-xl font-semibold tabular-nums"
        style={{ color }}
      >
        {value}%
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function AIReasoningPanel({ decision }: AIReasoningPanelProps) {
  if (!decision) {
    return (
      <section className="app-panel p-5 sm:p-6">
        <div className="flex items-center gap-2 mb-5">
          <Brain className="h-4 w-4 text-violet-400" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            AI Trade Decision
          </span>
        </div>
        <div className="app-inset px-5 py-10 text-center">
          <Brain className="mx-auto h-8 w-8 text-muted-foreground/40 mb-3" />
          <p className="text-sm text-muted-foreground max-w-sm mx-auto leading-6">
            No active AI decisions. The AI engine will display reasoning here
            when analyzing trade opportunities.
          </p>
        </div>
      </section>
    );
  }

  const { signal, checks, confidence, holdTime, timeline, timestamp } = decision;

  return (
    <section className="app-panel p-5 sm:p-6">
      {/* ── Signal Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Brain className="h-4 w-4 text-violet-400" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            AI Trade Decision
          </span>
        </div>
        {timestamp && (
          <span className="font-mono text-[10px] text-muted-foreground/70 tabular-nums">
            {timestamp}
          </span>
        )}
      </div>

      {/* ── Signal Trigger Block ────────────────────────────────────────── */}
      <div className="app-inset px-4 py-4 mb-4">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
          Signal Trigger
        </div>
        <div className="text-base font-semibold text-foreground">
          {signal.name}
        </div>
        <div className="mt-1.5 font-mono text-xs text-muted-foreground tabular-nums">
          {signal.detail}
        </div>
      </div>

      {/* ── Validation Checks ──────────────────────────────────────────── */}
      <div className="mb-4">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-3">
          Validation Checks
        </div>
        <div className="space-y-2">
          {checks.map((check) => {
            const Icon = STATUS_ICON[check.status];
            return (
              <div
                key={check.label}
                className="flex items-center gap-2.5 app-inset px-3.5 py-2.5"
              >
                <Icon className={cn("h-4 w-4 shrink-0", STATUS_COLOR[check.status])} />
                <span className="text-sm text-foreground">{check.label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Confidence Score ───────────────────────────────────────────── */}
      <div className="flex flex-col items-center py-4 mb-4 app-inset">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-3">
          Confidence Score
        </div>
        <ConfidenceRing value={confidence} />
      </div>

      {/* ── Expected Hold Time ─────────────────────────────────────────── */}
      {holdTime && (
        <div className="flex items-center gap-2 mb-4 px-1">
          <Clock className="h-3.5 w-3.5 text-muted-foreground/70" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Expected Hold
          </span>
          <span className="text-sm font-medium text-foreground ml-auto">
            {holdTime}
          </span>
        </div>
      )}

      {/* ── Decision Timeline ──────────────────────────────────────────── */}
      {timeline && timeline.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-3">
            Decision Timeline
          </div>
          <div className="relative pl-5">
            {/* Vertical connector line */}
            <div
              className="absolute left-[7px] top-2 bottom-2 w-px"
              style={{ background: "hsl(var(--border) / 0.6)" }}
            />
            <div className="space-y-3">
              {timeline.map((entry, idx) => (
                <div key={idx} className="relative flex items-start gap-3">
                  {/* Dot */}
                  <div
                    className="absolute -left-5 top-[5px] h-2.5 w-2.5 rounded-full border-2 border-violet-400 bg-background"
                  />
                  <span className="font-mono text-[11px] text-muted-foreground/80 tabular-nums shrink-0 min-w-[56px]">
                    {entry.time}
                  </span>
                  <span className="text-sm text-foreground leading-5">
                    {entry.event}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export type { AIDecision, AIReasoningPanelProps };
