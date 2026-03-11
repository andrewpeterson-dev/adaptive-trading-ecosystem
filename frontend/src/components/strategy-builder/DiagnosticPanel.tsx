"use client";

import React from "react";
import {
  AlertTriangle,
  AlertCircle,
  Info,
  Shield,
  CheckCircle2,
} from "lucide-react";
import type { DiagnosticReport } from "@/types/strategy";

interface DiagnosticPanelProps {
  report: DiagnosticReport | null;
  loading?: boolean;
}

const SEVERITY_CONFIG = {
  critical: {
    icon: AlertCircle,
    color: "text-red-400",
    bg: "bg-red-400/5 border-red-400/20",
    label: "Critical",
  },
  warning: {
    icon: AlertTriangle,
    color: "text-amber-400",
    bg: "bg-amber-400/5 border-amber-400/20",
    label: "Warning",
  },
  info: {
    icon: Info,
    color: "text-blue-400",
    bg: "bg-blue-400/5 border-blue-400/20",
    label: "Info",
  },
} as const;

function ScoreRing({ score }: { score: number }) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color =
    score >= 80 ? "text-emerald-400" : score >= 50 ? "text-amber-400" : "text-red-400";
  const strokeColor =
    score >= 80 ? "#34d399" : score >= 50 ? "#fbbf24" : "#f87171";

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg className="w-20 h-20 -rotate-90" viewBox="0 0 64 64">
        <circle
          cx="32"
          cy="32"
          r={radius}
          stroke="currentColor"
          strokeWidth="4"
          fill="none"
          className="text-muted/30"
        />
        <circle
          cx="32"
          cy="32"
          r={radius}
          stroke={strokeColor}
          strokeWidth="4"
          fill="none"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className={`text-lg font-bold ${color}`}>{score}</span>
        <span className="text-[9px] text-muted-foreground uppercase tracking-wider">
          Score
        </span>
      </div>
    </div>
  );
}

export function DiagnosticPanel({ report, loading }: DiagnosticPanelProps) {
  if (loading) {
    return (
      <div className="app-panel flex items-center justify-center p-6">
        <div className="animate-pulse flex items-center gap-2 text-muted-foreground">
          <Shield className="h-4 w-4" />
          <span className="text-sm">Running diagnostics...</span>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="app-panel flex items-center justify-center border-dashed p-6">
        <p className="text-sm text-muted-foreground">
          Add conditions to see diagnostics
        </p>
      </div>
    );
  }

  return (
    <div className="app-panel overflow-hidden">
      <div className="flex items-center gap-4 p-4 border-b border-border/50">
        <ScoreRing score={report.score} />
        <div>
          <h3 className="font-semibold flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary" />
            Strategy Health
          </h3>
          <p className="text-sm text-muted-foreground mt-0.5">
            {report.total_issues === 0 ? (
              <span className="text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" /> No issues detected
              </span>
            ) : (
              `${report.total_issues} issue${report.total_issues > 1 ? "s" : ""} found`
            )}
          </p>
        </div>
      </div>

      {report.diagnostics.length > 0 && (
        <div className="divide-y">
          {report.diagnostics.map((d, i) => {
            const cfg = SEVERITY_CONFIG[d.severity];
            const Icon = cfg.icon;

            return (
              <div key={i} className="p-4 space-y-1.5">
                <div className="flex items-start gap-2">
                  <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${cfg.color}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{d.title}</span>
                      <span
                        className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${cfg.bg} ${cfg.color}`}
                      >
                        {cfg.label}
                      </span>
                      <code className="text-[10px] text-muted-foreground font-mono">
                        {d.code}
                      </code>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
                      {d.message}
                    </p>
                    <p className="text-sm text-primary/80 mt-1">
                      {d.suggestion}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
