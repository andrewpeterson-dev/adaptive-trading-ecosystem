"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Sparkles,
  Loader2,
  ArrowRight,
  AlertTriangle,
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

const RECOMMENDATION_STYLES: Record<Recommendation, { label: string; className: string }> = {
  strong_buy: { label: "Strong Buy", className: "border-emerald-400/30 bg-emerald-500/15 text-emerald-300" },
  buy: { label: "Buy", className: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" },
  hold: { label: "Hold", className: "border-blue-500/25 bg-blue-500/10 text-blue-400" },
  sell: { label: "Sell", className: "border-orange-500/25 bg-orange-500/10 text-orange-400" },
  strong_sell: { label: "Strong Sell", className: "border-red-400/30 bg-red-500/15 text-red-300" },
};

function getRecommendationStyle(rec: string) {
  const key = rec.toLowerCase().replace(/\s+/g, "_") as Recommendation;
  return RECOMMENDATION_STYLES[key] ?? RECOMMENDATION_STYLES.hold;
}

// ── Widget Component ──────────────────────────────────────────────────

export function TradeAnalysisWidget() {
  const symbol = useTradeStore((state) => state.symbol);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TradeAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
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

  const recStyle = result ? getRecommendationStyle(result.recommendation) : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="app-label">Deep Analysis</p>
        {result && (
          <Link
            href="/trade-analysis"
            className="flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
          >
            Full Report
            <ArrowRight className="h-3 w-3" />
          </Link>
        )}
      </div>

      {/* Idle state: trigger button */}
      {!loading && !result && !error && (
        <button
          type="button"
          onClick={runAnalysis}
          disabled={!symbol.trim()}
          className={cn(
            "flex w-full items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-semibold transition-all",
            symbol.trim()
              ? "border-primary/25 bg-primary/8 text-primary hover:bg-primary/12 hover:border-primary/35"
              : "border-border/50 bg-muted/20 text-muted-foreground/50 cursor-not-allowed"
          )}
        >
          <Sparkles className="h-3.5 w-3.5" />
          Analyze {symbol || "..."}
        </button>
      )}

      {/* Loading state */}
      {loading && (
        <div className="rounded-xl border border-border/60 bg-muted/15 px-3 py-3">
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span className="text-xs font-medium text-foreground">Analyzing {symbol}...</span>
            <span className="ml-auto font-mono text-[11px] text-muted-foreground">
              {elapsedSeconds}s
            </span>
          </div>
          <div className="mt-2 app-progress-track h-1">
            <div
              className="app-progress-bar bg-primary h-1"
              style={{
                width: `${Math.min((elapsedSeconds / 60) * 100, 95)}%`,
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
            className="mt-2 text-[11px] font-medium text-primary hover:underline"
          >
            Retry
          </button>
        </div>
      )}

      {/* Result card */}
      {result && !loading && recStyle && (
        <div className="rounded-xl border border-border/60 bg-muted/15 px-3 py-3 space-y-2.5">
          {/* Recommendation badge */}
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em]",
                recStyle.className
              )}
            >
              {recStyle.label}
            </span>
            <span className="ml-auto font-mono text-xs font-semibold text-foreground">
              {result.confidence}%
            </span>
          </div>

          {/* Confidence bar */}
          <div className="app-progress-track h-1.5">
            <div
              className={cn(
                "app-progress-bar h-1.5",
                result.confidence >= 70
                  ? "bg-emerald-500"
                  : result.confidence >= 40
                    ? "bg-blue-500"
                    : "bg-orange-500"
              )}
              style={{ width: `${Math.min(result.confidence, 100)}%` }}
            />
          </div>

          {/* One-line reasoning */}
          <p className="text-[11px] leading-4 text-muted-foreground line-clamp-2">
            {result.reasoning}
          </p>

          {/* Actions */}
          <div className="flex items-center gap-2 pt-0.5">
            <Link
              href="/trade-analysis"
              className="flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
            >
              View Full Report
              <ArrowRight className="h-3 w-3" />
            </Link>
            <button
              type="button"
              onClick={runAnalysis}
              className="ml-auto text-[11px] text-muted-foreground hover:text-foreground"
            >
              Re-analyze
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
