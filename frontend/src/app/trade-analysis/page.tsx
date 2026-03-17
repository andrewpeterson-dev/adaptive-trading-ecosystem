"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import {
  BarChart3,
  Building2,
  MessageSquare,
  TrendingUp,
  TrendingDown,
  Shield,
  Brain,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Check,
  Loader2,
  AlertTriangle,
  Clock,
  ArrowRight,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { cn } from "@/lib/utils";

// ── Types ─────────────────────────────────────────────────────────────

interface TradeAnalysisResult {
  analysis_id: string;
  symbol: string;
  action: string;
  proposed_size: number;
  current_price: number;
  technical_report: string;
  fundamental_report: string;
  sentiment_report: string;
  bull_case: string;
  bear_case: string;
  risk_assessment: string;
  recommendation: string;
  confidence: number;
  reasoning: string;
  node_trace: string[];
  errors: string[];
}

type Recommendation = "strong_buy" | "buy" | "hold" | "sell" | "strong_sell";

// ── Constants ─────────────────────────────────────────────────────────

const ANALYSIS_STEPS = [
  "Technical Analyst",
  "Fundamental Analyst",
  "Sentiment Analyst",
  "Bull Researcher",
  "Bear Researcher",
  "Risk Assessor",
  "Decision Synthesizer",
] as const;

const REPORT_SECTIONS = [
  { key: "technical_report", title: "Technical Analysis", icon: BarChart3, color: "blue" },
  { key: "fundamental_report", title: "Fundamental Analysis", icon: Building2, color: "purple" },
  { key: "sentiment_report", title: "Sentiment Analysis", icon: MessageSquare, color: "cyan" },
  { key: "bull_case", title: "Bull Case", icon: TrendingUp, color: "green" },
  { key: "bear_case", title: "Bear Case", icon: TrendingDown, color: "red" },
  { key: "risk_assessment", title: "Risk Assessment", icon: Shield, color: "orange" },
  { key: "reasoning", title: "Final Decision", icon: Brain, color: "yellow" },
] as const;

const SECTION_COLORS: Record<string, { border: string; bg: string; text: string }> = {
  blue: { border: "border-l-blue-500", bg: "bg-blue-500/8", text: "text-blue-400" },
  purple: { border: "border-l-purple-500", bg: "bg-purple-500/8", text: "text-purple-400" },
  cyan: { border: "border-l-cyan-500", bg: "bg-cyan-500/8", text: "text-cyan-400" },
  green: { border: "border-l-emerald-500", bg: "bg-emerald-500/8", text: "text-emerald-400" },
  red: { border: "border-l-red-500", bg: "bg-red-500/8", text: "text-red-400" },
  orange: { border: "border-l-orange-500", bg: "bg-orange-500/8", text: "text-orange-400" },
  yellow: { border: "border-l-yellow-500", bg: "bg-yellow-500/8", text: "text-yellow-400" },
};

const RECOMMENDATION_STYLES: Record<Recommendation, { label: string; className: string }> = {
  strong_buy: { label: "Strong Buy", className: "border-emerald-400/30 bg-emerald-500/15 text-emerald-300" },
  buy: { label: "Buy", className: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400" },
  hold: { label: "Hold", className: "border-blue-500/25 bg-blue-500/10 text-blue-400" },
  sell: { label: "Sell", className: "border-orange-500/25 bg-orange-500/10 text-orange-400" },
  strong_sell: { label: "Strong Sell", className: "border-red-400/30 bg-red-500/15 text-red-300" },
};

// ── Helpers ───────────────────────────────────────────────────────────

function getRecommendationStyle(rec: string) {
  const key = rec.toLowerCase().replace(/\s+/g, "_") as Recommendation;
  return RECOMMENDATION_STYLES[key] ?? RECOMMENDATION_STYLES.hold;
}

function formatTimestamp(ts: string) {
  const d = new Date(ts);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// ── Page Component ────────────────────────────────────────────────────

export default function TradeAnalysisPage() {
  const [symbol, setSymbol] = useState("");
  const [action, setAction] = useState<"buy" | "sell">("buy");
  const [size, setSize] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState(-1);
  const [result, setResult] = useState<TradeAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(["reasoning"]));
  const [pastAnalyses, setPastAnalyses] = useState<TradeAnalysisResult[]>([]);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Simulated step progression during loading
  useEffect(() => {
    if (loading) {
      setActiveStep(0);
      setElapsedSeconds(0);
      const stepInterval = setInterval(() => {
        setActiveStep((prev) => {
          if (prev < ANALYSIS_STEPS.length - 1) return prev + 1;
          return prev;
        });
      }, 4500);
      timerRef.current = setInterval(() => {
        setElapsedSeconds((prev) => prev + 1);
      }, 1000);
      return () => {
        clearInterval(stepInterval);
        if (timerRef.current) clearInterval(timerRef.current);
      };
    } else {
      setActiveStep(-1);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  }, [loading]);

  const runAnalysis = useCallback(async () => {
    if (!symbol.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await apiFetch<TradeAnalysisResult>("/api/trade-analysis", {
        method: "POST",
        body: JSON.stringify({
          symbol: symbol.toUpperCase().trim(),
          action,
          size: parseFloat(size) || 100,
        }),
        cacheTtlMs: 0,
        timeoutMs: 120_000,
      });
      setResult(data);
      setExpandedSections(new Set(["reasoning"]));
      // Prepend to past analyses
      setPastAnalyses((prev) => [data, ...prev.filter((a) => a.analysis_id !== data.analysis_id)]);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Analysis failed. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [symbol, action, size]);

  const loadPastAnalysis = useCallback((analysis: TradeAnalysisResult) => {
    setResult(analysis);
    setSymbol(analysis.symbol);
    setAction(analysis.action as "buy" | "sell");
    setSize(String(analysis.proposed_size));
    setExpandedSections(new Set(["reasoning"]));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const toggleSection = useCallback((key: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const recStyle = result ? getRecommendationStyle(result.recommendation) : null;

  return (
    <div className="app-page">
      <SubNav
        items={[
          { href: "/trade", label: "Workspace" },
          { href: "/trade-analysis", label: "Deep Analysis" },
          { href: "/watchlist", label: "Watchlist" },
        ]}
      />

      <PageHeader
        eyebrow="Intelligence"
        title="Trade Analysis"
        description="Run multi-agent deep analysis on any trade. Seven AI analysts evaluate technical, fundamental, and sentiment signals to produce a comprehensive recommendation."
        badge={
          <span className="app-pill">
            <Brain className="h-3 w-3" />
            7-Node Agent
          </span>
        }
      />

      {/* ── Trigger Section ──────────────────────────────────────── */}
      <section className="app-panel">
        <div className="app-section-header">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-muted-foreground" />
            <h3 className="app-section-title">New Analysis</h3>
          </div>
        </div>
        <div className="p-4">
          <div className="flex flex-wrap items-end gap-3">
            {/* Ticker */}
            <div className="min-w-[120px] flex-1">
              <label className="app-label mb-1.5 block">Symbol</label>
              <input
                type="text"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                placeholder="AAPL"
                className="app-input h-10 font-mono text-sm uppercase"
                onKeyDown={(e) => e.key === "Enter" && runAnalysis()}
              />
            </div>

            {/* Buy/Sell toggle */}
            <div>
              <label className="app-label mb-1.5 block">Side</label>
              <div className="app-segmented">
                <button
                  type="button"
                  onClick={() => setAction("buy")}
                  className={cn(
                    "app-segment text-xs",
                    action === "buy" && "app-toggle-active bg-emerald-500/12 text-emerald-300 border border-emerald-500/25 rounded-full"
                  )}
                >
                  Buy
                </button>
                <button
                  type="button"
                  onClick={() => setAction("sell")}
                  className={cn(
                    "app-segment text-xs",
                    action === "sell" && "app-toggle-active bg-red-500/12 text-red-300 border border-red-500/25 rounded-full"
                  )}
                >
                  Sell
                </button>
              </div>
            </div>

            {/* Size */}
            <div className="min-w-[100px]">
              <label className="app-label mb-1.5 block">Shares</label>
              <input
                type="number"
                value={size}
                onChange={(e) => setSize(e.target.value)}
                placeholder="100"
                min={1}
                className="app-input h-10 font-mono text-sm"
              />
            </div>

            {/* Submit */}
            <Button
              variant="primary"
              size="md"
              onClick={runAnalysis}
              disabled={loading || !symbol.trim()}
              className="gap-2"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Brain className="h-4 w-4" />
              )}
              {loading ? "Analyzing..." : "Run Deep Analysis"}
            </Button>
          </div>

          {error && (
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-500/25 bg-red-500/8 px-3 py-2.5 text-sm text-red-300">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}
        </div>
      </section>

      {/* ── Loading Progress ─────────────────────────────────────── */}
      {loading && (
        <section className="app-panel">
          <div className="p-4">
            <div className="mb-3 flex items-center justify-between">
              <p className="app-label">Analysis in progress</p>
              <span className="font-mono text-xs text-muted-foreground">{elapsedSeconds}s</span>
            </div>
            <div className="space-y-2">
              {ANALYSIS_STEPS.map((step, i) => {
                const isDone = i < activeStep;
                const isActive = i === activeStep;
                return (
                  <div
                    key={step}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-300",
                      isDone && "text-emerald-400",
                      isActive && "bg-primary/8 text-primary",
                      !isDone && !isActive && "text-muted-foreground/50"
                    )}
                  >
                    {isDone ? (
                      <Check className="h-4 w-4 shrink-0 text-emerald-400" />
                    ) : isActive ? (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                    ) : (
                      <div className="h-4 w-4 shrink-0 rounded-full border border-border/50" />
                    )}
                    <span className="font-medium">{step}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* ── Results ──────────────────────────────────────────────── */}
      {result && (
        <div className="space-y-5">
          {/* Header card */}
          <section className="app-panel p-4 md:p-5">
            <div className="flex flex-wrap items-center gap-3">
              {/* Symbol */}
              <h2 className="text-2xl font-bold tracking-tight font-mono">{result.symbol}</h2>

              {/* Action badge */}
              <Badge
                variant={result.action.toLowerCase() === "buy" ? "success" : "danger"}
                className="text-xs uppercase"
              >
                {result.action}
              </Badge>

              {/* Recommendation badge */}
              {recStyle && (
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]",
                    recStyle.className
                  )}
                >
                  {recStyle.label}
                </span>
              )}

              <div className="ml-auto flex items-center gap-4 text-xs text-muted-foreground">
                {result.current_price > 0 && (
                  <span className="font-mono">${result.current_price.toFixed(2)}</span>
                )}
                <span className="font-mono">{result.proposed_size} shares</span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Now
                </span>
              </div>
            </div>

            {/* Confidence bar */}
            <div className="mt-4">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="app-label">Confidence</span>
                <span className="font-mono text-sm font-semibold text-foreground">
                  {result.confidence}%
                </span>
              </div>
              <div className="app-progress-track">
                <div
                  className={cn(
                    "app-progress-bar",
                    result.confidence >= 70
                      ? "bg-emerald-500"
                      : result.confidence >= 40
                        ? "bg-blue-500"
                        : "bg-orange-500"
                  )}
                  style={{ width: `${Math.min(result.confidence, 100)}%` }}
                />
              </div>
            </div>
          </section>

          {/* Accordion report sections */}
          <div className="space-y-2">
            {REPORT_SECTIONS.map(({ key, title, icon: Icon, color }) => {
              const content = result[key as keyof TradeAnalysisResult] as string;
              if (!content) return null;
              const isOpen = expandedSections.has(key);
              const colors = SECTION_COLORS[color];

              return (
                <section
                  key={key}
                  className={cn("app-panel overflow-hidden border-l-2", colors.border)}
                >
                  <button
                    type="button"
                    onClick={() => toggleSection(key)}
                    className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/20"
                  >
                    <div className={cn("flex h-7 w-7 items-center justify-center rounded-lg", colors.bg)}>
                      <Icon className={cn("h-4 w-4", colors.text)} />
                    </div>
                    <span className="flex-1 text-sm font-semibold text-foreground">{title}</span>
                    {isOpen ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </button>
                  <div
                    className={cn(
                      "grid transition-[grid-template-rows] duration-300 ease-in-out",
                      isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
                    )}
                  >
                    <div className="overflow-hidden">
                      <div className="border-t border-border/50 px-4 py-3">
                        <div className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                          {content}
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              );
            })}
          </div>

          {/* Node trace footer */}
          {(result.node_trace.length > 0 || result.errors.length > 0) && (
            <section className="app-panel p-4">
              {result.node_trace.length > 0 && (
                <div className="mb-3">
                  <p className="app-label mb-2">Execution Trace</p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {result.node_trace.map((node, i) => (
                      <React.Fragment key={i}>
                        <span className="rounded-md border border-border/60 bg-muted/30 px-2 py-0.5 text-[11px] font-mono text-muted-foreground">
                          {node}
                        </span>
                        {i < result.node_trace.length - 1 && (
                          <ArrowRight className="h-3 w-3 text-muted-foreground/40" />
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              )}
              {result.errors.length > 0 && (
                <div>
                  <p className="app-label mb-2 text-orange-400">Warnings</p>
                  <div className="space-y-1">
                    {result.errors.map((err, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs text-orange-300">
                        <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                        <span>{err}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      )}

      {/* ── Past Analyses ────────────────────────────────────────── */}
      {pastAnalyses.length > 0 && (
        <section className="app-panel">
          <div className="app-section-header">
            <h3 className="app-section-title">Recent Analyses</h3>
          </div>
          <div className="divide-y divide-border/50">
            {pastAnalyses.map((analysis) => {
              const style = getRecommendationStyle(analysis.recommendation);
              return (
                <button
                  key={analysis.analysis_id}
                  type="button"
                  onClick={() => loadPastAnalysis(analysis)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/20"
                >
                  <span className="font-mono text-sm font-semibold text-foreground w-16">
                    {analysis.symbol}
                  </span>
                  <Badge
                    variant={analysis.action.toLowerCase() === "buy" ? "success" : "danger"}
                    className="text-[10px] uppercase"
                  >
                    {analysis.action}
                  </Badge>
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em]",
                      style.className
                    )}
                  >
                    {style.label}
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {analysis.confidence}%
                  </span>
                  <span className="ml-auto text-[11px] text-muted-foreground">
                    {analysis.analysis_id ? formatTimestamp(new Date().toISOString()) : ""}
                  </span>
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
