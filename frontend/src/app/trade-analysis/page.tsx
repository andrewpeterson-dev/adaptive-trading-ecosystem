"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
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
  { label: "Technical Analyst", icon: BarChart3 },
  { label: "Fundamental Analyst", icon: Building2 },
  { label: "Sentiment Analyst", icon: MessageSquare },
  { label: "Bull Researcher", icon: TrendingUp },
  { label: "Bear Researcher", icon: TrendingDown },
  { label: "Risk Assessor", icon: Shield },
  { label: "Decision Synthesizer", icon: Brain },
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

const SECTION_COLORS: Record<string, { border: string; bg: string; text: string; openBg: string }> = {
  blue:   { border: "border-l-blue-500",    bg: "bg-blue-500/10",    text: "text-blue-400",    openBg: "bg-blue-500/[0.04]" },
  purple: { border: "border-l-purple-500",  bg: "bg-purple-500/10",  text: "text-purple-400",  openBg: "bg-purple-500/[0.04]" },
  cyan:   { border: "border-l-cyan-500",    bg: "bg-cyan-500/10",    text: "text-cyan-400",    openBg: "bg-cyan-500/[0.04]" },
  green:  { border: "border-l-emerald-500", bg: "bg-emerald-500/10", text: "text-emerald-400", openBg: "bg-emerald-500/[0.04]" },
  red:    { border: "border-l-red-500",     bg: "bg-red-500/10",     text: "text-red-400",     openBg: "bg-red-500/[0.04]" },
  orange: { border: "border-l-orange-500",  bg: "bg-orange-500/10",  text: "text-orange-400",  openBg: "bg-orange-500/[0.04]" },
  yellow: { border: "border-l-yellow-500",  bg: "bg-yellow-500/10",  text: "text-yellow-400",  openBg: "bg-yellow-500/[0.04]" },
};

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
    glowClass: "shadow-[0_0_16px_rgba(52,211,153,0.35)]",
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
    glowClass: "shadow-[0_0_16px_rgba(248,113,113,0.35)]",
  },
};

// ── Helpers ───────────────────────────────────────────────────────────

function getRecConfig(rec: string) {
  const key = rec.toLowerCase().replace(/\s+/g, "_") as Recommendation;
  return RECOMMENDATION_CONFIG[key] ?? RECOMMENDATION_CONFIG.hold;
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

function formatElapsed(secs: number) {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

// ── Sub-components ────────────────────────────────────────────────────

function RecommendationBadge({
  recommendation,
  size = "md",
}: {
  recommendation: string;
  size?: "sm" | "md" | "lg";
}) {
  const config = getRecConfig(recommendation);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border font-bold uppercase tracking-[0.12em]",
        config.badgeClass,
        config.glowClass,
        size === "sm" && "px-2 py-0.5 text-[9px]",
        size === "md" && "px-2.5 py-1 text-[11px]",
        size === "lg" && "px-3.5 py-1.5 text-[13px]",
      )}
    >
      {config.label}
    </span>
  );
}

function ConfidenceBar({
  confidence,
  recommendation,
  animated = true,
}: {
  confidence: number;
  recommendation: string;
  animated?: boolean;
}) {
  const [width, setWidth] = useState(animated ? 0 : confidence);
  const config = getRecConfig(recommendation);

  useEffect(() => {
    if (!animated) return;
    const t = setTimeout(() => setWidth(confidence), 80);
    return () => clearTimeout(t);
  }, [confidence, animated]);

  return (
    <div className="app-progress-track h-2">
      <div
        className={cn("app-progress-bar h-2", config.barClass)}
        style={{
          width: `${Math.min(width, 100)}%`,
          transition: animated ? "width 0.8s cubic-bezier(0.4, 0, 0.2, 1)" : undefined,
        }}
      />
    </div>
  );
}

function AccordionSection({
  sectionKey,
  title,
  icon: Icon,
  color,
  content,
  isOpen,
  onToggle,
}: {
  sectionKey: string;
  title: string;
  icon: React.ElementType;
  color: string;
  content: string;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const colors = SECTION_COLORS[color];

  return (
    <section
      className={cn(
        "overflow-hidden rounded-xl border border-l-2 backdrop-blur-xl transition-colors duration-200",
        "border-border/72",
        colors.border,
        isOpen ? colors.openBg : "bg-transparent",
      )}
      style={{
        background: isOpen
          ? undefined
          : "linear-gradient(180deg, hsl(var(--surface-2) / 0.92), hsl(var(--surface-3) / 0.92))",
      }}
    >
      <button
        type="button"
        onClick={onToggle}
        className={cn(
          "flex w-full items-center gap-3 px-4 py-3.5 text-left",
          "transition-colors duration-150 hover:bg-white/5",
        )}
        aria-expanded={isOpen}
      >
        <div className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-lg", colors.bg)}>
          <Icon className={cn("h-4 w-4", colors.text)} />
        </div>
        <span className="flex-1 text-sm font-semibold text-foreground">{title}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-300 ease-in-out",
            isOpen && "rotate-180",
          )}
        />
      </button>

      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-300 ease-in-out",
          isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden">
          <div className="border-t border-border/40 px-4 py-4">
            <p className="max-w-3xl whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
              {content}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function NodeTrace({ nodes, errors }: { nodes: string[]; errors: string[] }) {
  const errorSet = new Set(errors.map((e) => e.toLowerCase()));

  return (
    <section className="app-panel p-4">
      {nodes.length > 0 && (
        <div className="mb-3 last:mb-0">
          <p className="app-label mb-3">Execution Trace</p>
          <div className="flex flex-wrap items-center gap-0">
            {nodes.map((node, i) => {
              const isError = errorSet.has(node.toLowerCase());
              const isLast = i === nodes.length - 1;
              return (
                <React.Fragment key={i}>
                  <div className="flex flex-col items-center gap-1">
                    <div
                      className={cn(
                        "flex h-6 w-6 items-center justify-center rounded-full border text-[10px] font-bold",
                        isError
                          ? "border-red-500/40 bg-red-500/15 text-red-400"
                          : "border-emerald-500/35 bg-emerald-500/12 text-emerald-400",
                      )}
                    >
                      {isError ? "!" : <Check className="h-3 w-3" />}
                    </div>
                    <span
                      className={cn(
                        "max-w-[72px] text-center font-mono text-[9px] leading-tight",
                        isError ? "text-red-400" : "text-muted-foreground",
                      )}
                    >
                      {node}
                    </span>
                  </div>
                  {!isLast && (
                    <div className="mb-4 h-px w-4 shrink-0 bg-border/50 sm:w-6" />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      )}
      {errors.length > 0 && (
        <div className="mt-3 border-t border-border/40 pt-3">
          <p className="app-label mb-2 text-orange-400">Warnings</p>
          <div className="space-y-1">
            {errors.map((err, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-orange-300">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                <span>{err}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function EmptyState() {
  return (
    <section className="app-panel">
      <div className="flex flex-col items-center gap-5 px-6 py-16 text-center sm:py-20">
        {/* Animated brain icon */}
        <div className="relative">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-primary/20 bg-primary/8">
            <Brain className="h-8 w-8 text-primary/70" />
          </div>
          <div className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full border border-primary/30 bg-primary/12">
            <Sparkles className="h-2.5 w-2.5 text-primary" />
          </div>
        </div>

        <div className="max-w-sm space-y-2">
          <h3 className="text-base font-semibold text-foreground">
            Run a Deep Analysis
          </h3>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Enter a ticker above and seven AI analysts will evaluate technical signals,
            fundamentals, sentiment, bull/bear cases, risk, and synthesize a final recommendation.
          </p>
        </div>

        {/* Step preview pills */}
        <div className="flex flex-wrap justify-center gap-1.5 pt-1">
          {ANALYSIS_STEPS.map(({ label, icon: Icon }) => (
            <div
              key={label}
              className="flex items-center gap-1.5 rounded-full border border-border/60 bg-muted/20 px-2.5 py-1 text-[11px] text-muted-foreground/70"
            >
              <Icon className="h-3 w-3" />
              {label}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Loading Progress ───────────────────────────────────────────────────

function AnalysisProgress({
  activeStep,
  elapsedSeconds,
}: {
  activeStep: number;
  elapsedSeconds: number;
}) {
  const progress = ((activeStep + 1) / ANALYSIS_STEPS.length) * 100;

  return (
    <section className="app-panel overflow-hidden">
      {/* Top progress bar */}
      <div className="h-0.5 w-full bg-border/30">
        <div
          className="h-full bg-gradient-to-r from-primary/60 to-primary transition-[width] duration-700 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="p-4 sm:p-5">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm font-semibold text-foreground">Analysis in progress</p>
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {formatElapsed(elapsedSeconds)}
          </span>
        </div>

        <div className="space-y-1">
          {ANALYSIS_STEPS.map(({ label, icon: Icon }, i) => {
            const isDone = i < activeStep;
            const isActive = i === activeStep;
            const isPending = !isDone && !isActive;

            return (
              <div
                key={label}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-300",
                  isDone && "text-emerald-400",
                  isActive && "bg-primary/8 text-primary",
                  isPending && "text-muted-foreground/40",
                )}
              >
                {/* Step indicator */}
                <div className="relative h-5 w-5 shrink-0">
                  {isDone && (
                    <div className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 animate-[scale-in_250ms_ease-out_forwards]">
                      <Check className="h-3 w-3 text-emerald-400" strokeWidth={3} />
                    </div>
                  )}
                  {isActive && (
                    <div className="flex h-5 w-5 items-center justify-center">
                      <div className="h-2 w-2 rounded-full bg-primary animate-[pulse-dot_1.4s_ease-in-out_infinite]" />
                    </div>
                  )}
                  {isPending && (
                    <div className="flex h-5 w-5 items-center justify-center">
                      <div className="h-1.5 w-1.5 rounded-full bg-border" />
                    </div>
                  )}
                </div>

                {/* Icon */}
                <Icon
                  className={cn(
                    "h-3.5 w-3.5 shrink-0",
                    isDone && "text-emerald-400/70",
                    isActive && "text-primary",
                    isPending && "text-muted-foreground/30",
                  )}
                />

                <span className="font-medium">{label}</span>

                {isActive && (
                  <span className="ml-auto text-[11px] text-primary/60 animate-pulse">
                    Working...
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
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
  const [pastAnalyses, setPastAnalyses] = useState<(TradeAnalysisResult & { created_at?: string })[]>([]);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (loading) {
      setActiveStep(0);
      setElapsedSeconds(0);
      const stepInterval = setInterval(() => {
        setActiveStep((prev) => (prev < ANALYSIS_STEPS.length - 1 ? prev + 1 : prev));
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
      setPastAnalyses((prev) => [
        { ...data, created_at: new Date().toISOString() },
        ...prev.filter((a) => a.analysis_id !== data.analysis_id),
      ]);
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
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const recConfig = result ? getRecConfig(result.recommendation) : null;

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
                    action === "buy" && "app-toggle-active bg-emerald-500/12 text-emerald-300 border border-emerald-500/25 rounded-full",
                  )}
                >
                  Buy
                </button>
                <button
                  type="button"
                  onClick={() => setAction("sell")}
                  className={cn(
                    "app-segment text-xs",
                    action === "sell" && "app-toggle-active bg-red-500/12 text-red-300 border border-red-500/25 rounded-full",
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
        <AnalysisProgress activeStep={activeStep} elapsedSeconds={elapsedSeconds} />
      )}

      {/* ── Empty state ───────────────────────────────────────────── */}
      {!loading && !result && !error && <EmptyState />}

      {/* ── Results ──────────────────────────────────────────────── */}
      {result && (
        <div className="space-y-4">
          {/* Header card */}
          <section className="app-panel p-4 md:p-5">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-mono text-2xl font-bold tracking-tight">{result.symbol}</h2>

              <Badge
                variant={result.action.toLowerCase() === "buy" ? "success" : "danger"}
                className="text-xs uppercase"
              >
                {result.action}
              </Badge>

              {recConfig && (
                <RecommendationBadge recommendation={result.recommendation} size="md" />
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

            {/* Confidence */}
            <div className="mt-4 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="app-label">Confidence</span>
                <span className="font-mono text-sm font-semibold tabular-nums text-foreground">
                  {result.confidence}%
                </span>
              </div>
              <ConfidenceBar
                confidence={result.confidence}
                recommendation={result.recommendation}
                animated
              />
            </div>
          </section>

          {/* Accordion sections */}
          <div className="space-y-2">
            {REPORT_SECTIONS.map(({ key, title, icon, color }) => {
              const content = result[key as keyof TradeAnalysisResult] as string;
              if (!content) return null;
              return (
                <AccordionSection
                  key={key}
                  sectionKey={key}
                  title={title}
                  icon={icon}
                  color={color}
                  content={content}
                  isOpen={expandedSections.has(key)}
                  onToggle={() => toggleSection(key)}
                />
              );
            })}
          </div>

          {/* Node trace */}
          {(result.node_trace.length > 0 || result.errors.length > 0) && (
            <NodeTrace nodes={result.node_trace} errors={result.errors} />
          )}
        </div>
      )}

      {/* ── Past Analyses ────────────────────────────────────────── */}
      {pastAnalyses.length > 0 && (
        <section className="app-panel">
          <div className="app-section-header">
            <h3 className="app-section-title">Recent Analyses</h3>
            <span className="text-[11px] text-muted-foreground">{pastAnalyses.length} run{pastAnalyses.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="divide-y divide-border/50">
            {pastAnalyses.map((analysis) => (
              <button
                key={analysis.analysis_id}
                type="button"
                onClick={() => loadPastAnalysis(analysis)}
                className={cn(
                  "flex w-full items-center gap-3 px-4 py-3 text-left",
                  "transition-colors duration-150 hover:bg-muted/20",
                  result?.analysis_id === analysis.analysis_id && "bg-primary/5",
                )}
              >
                <span className="w-16 font-mono text-sm font-semibold text-foreground">
                  {analysis.symbol}
                </span>
                <Badge
                  variant={analysis.action.toLowerCase() === "buy" ? "success" : "danger"}
                  className="text-[10px] uppercase"
                >
                  {analysis.action}
                </Badge>
                <RecommendationBadge recommendation={analysis.recommendation} size="sm" />
                <span className="font-mono text-xs tabular-nums text-muted-foreground">
                  {analysis.confidence}%
                </span>
                <span className="ml-auto text-[11px] text-muted-foreground">
                  {analysis.created_at ? formatTimestamp(analysis.created_at) : ""}
                </span>
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/50" />
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
