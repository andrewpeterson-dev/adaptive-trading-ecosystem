"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Brain,
  Sparkles,
  Loader2,
  ArrowRight,
  AlertTriangle,
  RotateCcw,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { useTradeStore } from "@/stores/trade-store";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────

interface TradeAnalysisResult {
  analysis_id: string;
  symbol: string;
  action: string;
  proposed_size: number;
  current_price: number;
  recommendation: string;
  confidence: number;
  reasoning: string;
  technical_report: string;
  fundamental_report: string;
  sentiment_report: string;
  bull_case: string;
  bear_case: string;
  risk_assessment: string;
  node_trace: string[];
  errors: string[];
}

type Recommendation = "strong_buy" | "buy" | "hold" | "sell" | "strong_sell";

const RECOMMENDATION_CONFIG: Record<Recommendation, {
  label: string;
  badgeClass: string;
  barClass: string;
  glowClass: string;
}> = {
  strong_buy: {
    label: "Strong Buy",
    badgeClass: "border-emerald-400/40 bg-emerald-500/15 text-emerald-300",
    barClass: "bg-gradient-to-r from-emerald-500 to-emerald-400",
    glowClass: "shadow-[0_0_12px_rgba(52,211,153,0.3)]",
  },
  buy: {
    label: "Buy",
    badgeClass: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
    barClass: "bg-gradient-to-r from-emerald-600 to-emerald-500",
    glowClass: "",
  },
  hold: {
    label: "Hold",
    badgeClass: "border-blue-500/30 bg-blue-500/10 text-blue-400",
    barClass: "bg-gradient-to-r from-blue-600 to-blue-500",
    glowClass: "",
  },
  sell: {
    label: "Sell",
    badgeClass: "border-orange-500/30 bg-orange-500/10 text-orange-400",
    barClass: "bg-gradient-to-r from-orange-600 to-orange-500",
    glowClass: "",
  },
  strong_sell: {
    label: "Strong Sell",
    badgeClass: "border-red-400/40 bg-red-500/15 text-red-300",
    barClass: "bg-gradient-to-r from-red-500 to-red-400",
    glowClass: "shadow-[0_0_12px_rgba(248,113,113,0.3)]",
  },
};

function getRecConfig(rec: string) {
  const key = rec.toLowerCase().replace(/\s+/g, "_") as Recommendation;
  return RECOMMENDATION_CONFIG[key] ?? RECOMMENDATION_CONFIG.hold;
}

function formatElapsed(secs: number) {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

// ── Widget Component ──────────────────────────────────────────────────

export function TradeAnalysisWidget() {
  const symbol = useTradeStore((state) => state.symbol);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TradeAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [barWidth, setBarWidth] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastAnalyzedSymbol = useRef<string>("");

  // Reset when symbol changes
  useEffect(() => {
    if (symbol !== lastAnalyzedSymbol.current) {
      setResult(null);
      setError(null);
    }
  }, [symbol]);

  // Elapsed timer
  useEffect(() => {
    if (loading) {
      setElapsedSeconds(0);
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
      };
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
  }, [loading]);

  // Animate confidence bar on result
  useEffect(() => {
    if (result) {
      setBarWidth(0);
      const t = setTimeout(() => setBarWidth(result.confidence), 80);
      return () => clearTimeout(t);
    }
  }, [result]);

  const runAnalysis = useCallback(async () => {
    if (!symbol.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    lastAnalyzedSymbol.current = symbol;

    try {
      const data = await apiFetch<TradeAnalysisResult>("/api/trade-analysis", {
        method: "POST",
        body: JSON.stringify({
          symbol: symbol.toUpperCase().trim(),
          action: "buy",
          size: 100,
        }),
        cacheTtlMs: 0,
        timeoutMs: 120_000,
      });
      setResult(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Analysis failed.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [symbol, loading]);

  const recConfig = result ? getRecConfig(result.recommendation) : null;
  const loadingBarWidth = Math.min((elapsedSeconds / 60) * 100, 92);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="app-label">Deep Analysis</p>
        {result && (
          <Link
            href="/trade-analysis"
            className="group flex items-center gap-1 text-[11px] font-medium text-primary transition-colors hover:text-primary/80"
          >
            Full Report
            <ArrowRight className="h-3 w-3 transition-transform duration-150 group-hover:translate-x-0.5" />
          </Link>
        )}
      </div>

      {/* Idle: trigger button */}
      {!loading && !result && !error && (
        <button
          type="button"
          onClick={runAnalysis}
          disabled={!symbol.trim()}
          className={cn(
            "group flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-semibold transition-all duration-200",
            symbol.trim()
              ? "border-primary/25 bg-primary/8 text-primary hover:bg-primary/14 hover:border-primary/40 hover:shadow-[0_0_16px_rgba(59,130,246,0.15)]"
              : "cursor-not-allowed border-border/50 bg-muted/20 text-muted-foreground/50",
          )}
        >
          <Brain
            className={cn(
              "h-3.5 w-3.5 transition-transform duration-300",
              symbol.trim() && "group-hover:scale-110",
            )}
          />
          Analyze {symbol || "..."}
          {symbol.trim() && (
            <Sparkles className="h-3 w-3 opacity-60" />
          )}
        </button>
      )}

      {/* Loading state */}
      {loading && (
        <div className="overflow-hidden rounded-xl border border-primary/20 bg-primary/5">
          <div className="flex items-center gap-2.5 px-3 pt-3">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
            <span className="flex-1 text-xs font-medium text-foreground">
              Analyzing {symbol}…
            </span>
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
              {formatElapsed(elapsedSeconds)}
            </span>
          </div>
          {/* Progress bar */}
          <div className="mx-3 mb-3 mt-2 h-1 overflow-hidden rounded-full bg-border/40">
            <div
              className="h-full rounded-full bg-gradient-to-r from-primary/70 to-primary"
              style={{
                width: `${loadingBarWidth}%`,
                transition: "width 1s linear",
              }}
            />
          </div>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="rounded-xl border border-red-500/25 bg-red-500/8 px-3 py-2.5">
          <div className="flex items-center gap-2 text-xs text-red-300">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            <span className="flex-1 truncate">{error}</span>
          </div>
          <button
            type="button"
            onClick={runAnalysis}
            className="mt-2 flex items-center gap-1 text-[11px] font-medium text-primary transition-colors hover:text-primary/80"
          >
            <RotateCcw className="h-2.5 w-2.5" />
            Retry
          </button>
        </div>
      )}

      {/* Result card */}
      {result && !loading && recConfig && (
        <div className="overflow-hidden rounded-xl border border-border/60 bg-muted/10">
          {/* Recommendation row */}
          <div className="flex items-center gap-2 px-3 pt-3">
            <span
              className={cn(
                "inline-flex items-center rounded-md border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em]",
                recConfig.badgeClass,
                recConfig.glowClass,
              )}
            >
              {recConfig.label}
            </span>
            <span className="ml-auto font-mono text-xs font-semibold tabular-nums text-foreground">
              {result.confidence}%
            </span>
          </div>

          {/* Confidence bar */}
          <div className="mx-3 mt-2 h-1.5 overflow-hidden rounded-full bg-border/40">
            <div
              className={cn("h-full rounded-full", recConfig.barClass)}
              style={{
                width: `${Math.min(barWidth, 100)}%`,
                transition: "width 0.8s cubic-bezier(0.4, 0, 0.2, 1)",
              }}
            />
          </div>

          {/* Reasoning snippet */}
          <p className="mx-3 mt-2 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
            {result.reasoning}
          </p>

          {/* Footer actions */}
          <div className="flex items-center gap-2 border-t border-border/40 px-3 py-2 mt-2">
            <Link
              href="/trade-analysis"
              className="group flex items-center gap-1 text-[11px] font-semibold text-primary transition-colors hover:text-primary/80"
            >
              View Full Report
              <ArrowRight className="h-3 w-3 transition-transform duration-150 group-hover:translate-x-0.5" />
            </Link>
            <button
              type="button"
              onClick={runAnalysis}
              className="ml-auto flex items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
            >
              <RotateCcw className="h-2.5 w-2.5" />
              Re-analyze
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
