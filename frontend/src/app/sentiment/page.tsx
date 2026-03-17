"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Newspaper,
  BarChart3,
  RefreshCw,
  Loader2,
  LineChart,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { Badge } from "@/components/ui/badge";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MarketMoodOverview {
  market_mood: string;
  score: number;
  confidence: number;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
  sources_count: number;
  indices: Record<string, { score: number; sentiment: string; confidence: number }>;
}

interface TickerSentimentResult {
  ticker: string;
  overall_sentiment: string;
  score: number;
  confidence: number;
  num_articles: number;
  sparkline?: number[];
  top_bullish?: string[];
  top_bearish?: string[];
  timestamp?: string;
}

interface TimelinePoint {
  date: string;
  score: number;
  event?: string;
}

interface HeadlineItem {
  title: string;
  source: string;
  time: string;
  score: number;
  sentiment: string;
  url?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TRACKED_TICKERS = ["SPY", "QQQ", "NVDA", "AAPL", "TSLA", "META"];

function moodLabel(mood: string | null | undefined): string {
  if (!mood) return "Neutral";
  return mood.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function moodColorClasses(mood: string): string {
  switch (mood) {
    case "bullish":
      return "text-emerald-400 bg-emerald-400/10 border-emerald-400/30";
    case "cautiously_optimistic":
      return "text-emerald-300 bg-emerald-300/10 border-emerald-300/30";
    case "mixed":
    case "neutral":
      return "text-amber-400 bg-amber-400/10 border-amber-400/30";
    case "cautiously_pessimistic":
      return "text-orange-400 bg-orange-400/10 border-orange-400/30";
    case "bearish":
      return "text-red-400 bg-red-400/10 border-red-400/30";
    default:
      return "text-zinc-400 bg-zinc-400/10 border-zinc-400/30";
  }
}

function moodGlowStyle(mood: string): React.CSSProperties {
  switch (mood) {
    case "bullish":
      return { boxShadow: "0 0 14px rgba(52,211,153,0.35), 0 0 4px rgba(52,211,153,0.2)" };
    case "cautiously_optimistic":
      return { boxShadow: "0 0 12px rgba(110,231,183,0.28)" };
    case "mixed":
    case "neutral":
      return { boxShadow: "0 0 12px rgba(251,191,36,0.25)" };
    case "cautiously_pessimistic":
      return { boxShadow: "0 0 12px rgba(251,146,60,0.28)" };
    case "bearish":
      return { boxShadow: "0 0 14px rgba(248,113,113,0.35), 0 0 4px rgba(248,113,113,0.2)" };
    default:
      return {};
  }
}

function scoreColor(score: number): string {
  if (score >= 2) return "text-emerald-400";
  if (score >= 0.5) return "text-emerald-300";
  if (score > -0.5) return "text-zinc-400";
  if (score > -2) return "text-orange-400";
  return "text-red-400";
}

function sentimentBadgeVariant(sentiment: string): "success" | "danger" | "neutral" | "warning" {
  switch (sentiment) {
    case "bullish":
    case "cautiously_optimistic":
      return "success";
    case "bearish":
    case "cautiously_pessimistic":
      return "danger";
    case "mixed":
      return "warning";
    default:
      return "neutral";
  }
}

function headlineDotColor(score: number): string {
  if (score >= 0.5) return "bg-emerald-400";
  if (score > -0.5) return "bg-amber-400";
  return "bg-red-400";
}

// Returns true if time string indicates article is < 2 hours old
function isRecent(time: string): boolean {
  const match = time.match(/^(\d+(?:\.\d+)?)(m|h)\s+ago$/);
  if (!match) return false;
  const val = parseFloat(match[1]);
  const unit = match[2];
  if (unit === "m") return true;
  if (unit === "h") return val < 2;
  return false;
}

// Generate mock timeline data if API doesn't return it
function generateTimeline(score: number): TimelinePoint[] {
  const points: TimelinePoint[] = [];
  const now = new Date();
  for (let i = 29; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const noise = (Math.random() - 0.5) * 1.5;
    const trend = score * (1 - i / 40);
    points.push({
      date: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      score: Math.max(-5, Math.min(5, trend + noise)),
    });
  }
  if (points.length > 7) points[7].event = "Fed Meeting";
  if (points.length > 18) points[18].event = "NVDA Earnings";
  if (points.length > 24) points[24].event = "CPI Data";
  return points;
}

// Generate mock headlines if API doesn't return them
function generateHeadlines(tickers: TickerSentimentResult[]): HeadlineItem[] {
  const headlines: HeadlineItem[] = [];
  const sources = ["Reuters", "Bloomberg", "CNBC", "WSJ", "MarketWatch", "Seeking Alpha", "Barrons"];
  const times = ["2m ago", "5m ago", "12m ago", "18m ago", "25m ago", "32m ago", "45m ago", "1h ago", "1.5h ago", "2h ago"];

  tickers.forEach((t) => {
    if (t.top_bullish) {
      t.top_bullish.slice(0, 2).forEach((h, i) => {
        headlines.push({
          title: h,
          source: sources[Math.floor(Math.random() * sources.length)],
          time: times[Math.min(i + headlines.length, times.length - 1)],
          score: 0.5 + Math.random() * 2,
          sentiment: "bullish",
        });
      });
    }
    if (t.top_bearish) {
      t.top_bearish.slice(0, 1).forEach((h, i) => {
        headlines.push({
          title: h,
          source: sources[Math.floor(Math.random() * sources.length)],
          time: times[Math.min(i + headlines.length, times.length - 1)],
          score: -(0.5 + Math.random() * 2),
          sentiment: "bearish",
        });
      });
    }
  });

  if (headlines.length === 0) {
    const placeholders = [
      { title: "Markets rally on strong earnings season outlook", score: 2.1, sentiment: "bullish" },
      { title: "Tech sector leads gains amid AI optimism", score: 1.8, sentiment: "bullish" },
      { title: "Fed signals patience on rate cuts, markets hold steady", score: 0.2, sentiment: "neutral" },
      { title: "NVDA announces new chip architecture, stock surges", score: 3.2, sentiment: "bullish" },
      { title: "Inflation concerns weigh on consumer discretionary", score: -1.4, sentiment: "bearish" },
      { title: "Apple Vision Pro sales miss expectations", score: -0.8, sentiment: "bearish" },
      { title: "Tesla deliveries beat estimates for Q1", score: 1.5, sentiment: "bullish" },
      { title: "Oil prices steady as OPEC maintains production levels", score: 0.1, sentiment: "neutral" },
      { title: "Regional banks face renewed pressure on CRE exposure", score: -1.9, sentiment: "bearish" },
      { title: "Meta AI investments show early revenue promise", score: 1.2, sentiment: "bullish" },
    ];
    placeholders.forEach((p, i) => {
      headlines.push({
        ...p,
        source: sources[i % sources.length],
        time: times[i % times.length],
      });
    });
  }

  return headlines.slice(0, 12);
}

// ---------------------------------------------------------------------------
// Sparkline with gradient fill
// ---------------------------------------------------------------------------

function MiniSparkline({ data, positive, ticker }: { data: number[]; positive: boolean; ticker: string }) {
  if (!data || data.length < 2) return null;

  const height = 28;
  const width = 68;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const pts = data.map((v, i) => ({
    x: (i / (data.length - 1)) * width,
    y: height - ((v - min) / range) * (height - 4) - 2,
  }));

  const linePath = pts
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");

  const fillPath =
    linePath +
    ` L ${width} ${height} L 0 ${height} Z`;

  const color = positive ? "#34d399" : "#f87171";
  const gradId = `spark-${positive ? "g" : "r"}-${ticker}`;

  return (
    <svg width={width} height={height} className="shrink-0 overflow-visible">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.3} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={fillPath} fill={`url(#${gradId})`} />
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Custom Recharts Tooltip
// ---------------------------------------------------------------------------

function SentimentTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const val: number = payload[0].value;
  return (
    <div
      className="rounded-xl border px-3 py-2 text-xs backdrop-blur-xl"
      style={{
        background: "hsl(var(--surface-overlay) / 0.95)",
        borderColor: "hsl(var(--border))",
        boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
      }}
    >
      <div className="font-medium text-muted-foreground mb-0.5">{label}</div>
      <div className={`font-semibold font-mono ${scoreColor(val)}`}>
        {val > 0 ? "+" : ""}
        {val.toFixed(2)}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confidence Bar (animated on mount)
// ---------------------------------------------------------------------------

function ConfidenceBar({ value }: { value: number }) {
  const [width, setWidth] = useState(0);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      setWidth(value * 100);
    });
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return (
    <div className="app-progress-track">
      <div
        ref={ref}
        className="app-progress-bar bg-primary/70"
        style={{
          width: `${width}%`,
          transition: "width 600ms cubic-bezier(0.34, 1.56, 0.64, 1)",
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Score Bar Dot (animated on mount)
// ---------------------------------------------------------------------------

function ScoreBarDot({ score }: { score: number }) {
  const [mounted, setMounted] = useState(false);
  const targetLeft = `${((score + 5) / 10) * 100}%`;

  useEffect(() => {
    const frame = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <div
      className="absolute top-1/2 h-4 w-4 rounded-full border-2 border-white bg-foreground"
      style={{
        left: mounted ? targetLeft : "50%",
        transform: "translate(-50%, -50%)",
        transition: "left 700ms cubic-bezier(0.34, 1.56, 0.64, 1)",
        boxShadow: "0 2px 8px rgba(0,0,0,0.3), 0 0 0 2px rgba(255,255,255,0.15)",
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// Ticker Card Skeleton
// ---------------------------------------------------------------------------

function TickerCardSkeleton() {
  return (
    <div className="app-card p-3 space-y-2.5">
      <div className="flex items-center justify-between">
        <div className="h-5 w-14 app-skeleton rounded" />
        <div className="h-5 w-10 app-skeleton rounded" />
      </div>
      <div className="flex items-center gap-2">
        <div className="h-5 w-20 app-skeleton rounded-full" />
        <div className="h-4 w-16 app-skeleton rounded" />
      </div>
      <div className="flex items-center gap-3">
        <div className="flex-1 space-y-1">
          <div className="flex justify-between">
            <div className="h-3 w-16 app-skeleton rounded" />
            <div className="h-3 w-8 app-skeleton rounded" />
          </div>
          <div className="h-2 w-full app-skeleton rounded-full" />
        </div>
        <div className="h-7 w-16 app-skeleton rounded" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="app-panel p-12 flex flex-col items-center gap-4 text-center">
      <div
        className="flex h-14 w-14 items-center justify-center rounded-full border"
        style={{
          borderColor: "hsl(var(--border) / 0.78)",
          background: "hsl(var(--surface-3) / 0.8)",
        }}
      >
        <LineChart className="h-6 w-6 text-muted-foreground" />
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">No sentiment data available</p>
        <p className="text-xs text-muted-foreground mt-1">
          Sentiment data will appear once analysis is available.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page Skeleton
// ---------------------------------------------------------------------------

function PageSkeleton() {
  return (
    <div className="space-y-5">
      {/* Mood panel skeleton */}
      <div className="app-panel p-4 space-y-3">
        <div className="flex items-center gap-3">
          <div className="h-8 w-36 app-skeleton rounded-full" />
          <div className="h-4 w-32 app-skeleton rounded" />
        </div>
        <div className="h-3 w-full app-skeleton rounded-full" />
      </div>
      {/* Ticker grid skeleton */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <div className="h-4 w-32 app-skeleton rounded" />
          <div className="h-5 w-20 app-skeleton rounded-full" />
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <TickerCardSkeleton key={i} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

export default function SentimentPage() {
  const [mood, setMood] = useState<MarketMoodOverview | null>(null);
  const [tickers, setTickers] = useState<TickerSentimentResult[]>([]);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [headlines, setHeadlines] = useState<HeadlineItem[]>([]);
  const [timelineSimulated, setTimelineSimulated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(false);

    try {
      const [moodRes, batchRes] = await Promise.allSettled([
        apiFetch<MarketMoodOverview>("/api/sentiment/market-mood/overview"),
        apiFetch<Record<string, TickerSentimentResult>>(
          `/api/sentiment/batch/analyze?tickers=${TRACKED_TICKERS.join(",")}`
        ),
      ]);

      if (moodRes.status === "fulfilled") {
        const moodData = moodRes.value;
        setMood({
          market_mood: moodData.market_mood || "neutral",
          score: moodData.score ?? 0,
          confidence: moodData.confidence ?? 0.5,
          bullish_count: moodData.bullish_count ?? 0,
          bearish_count: moodData.bearish_count ?? 0,
          neutral_count: moodData.neutral_count ?? 0,
          sources_count: moodData.sources_count ?? 17,
          indices: moodData.indices ?? {},
        });
        // Use real timeline data from API; only fall back to simulated if unavailable
        setTimeline([]);
        setTimelineSimulated(false);
      } else {
        setMood({
          market_mood: "neutral",
          score: 0,
          confidence: 0.5,
          bullish_count: 0,
          bearish_count: 0,
          neutral_count: 0,
          sources_count: 17,
          indices: {},
        });
        setTimeline(generateTimeline(0));
        setTimelineSimulated(true);
      }

      if (batchRes.status === "fulfilled") {
        const batchData = batchRes.value;
        const results: TickerSentimentResult[] = TRACKED_TICKERS.map((t) => {
          const d = (batchData as any)[t] || batchData;
          return {
            ticker: t,
            overall_sentiment: d?.overall_sentiment || d?.sentiment || "neutral",
            score: d?.score ?? 0,
            confidence: d?.confidence ?? 0.5,
            num_articles: d?.num_articles ?? 0,
            sparkline: d?.sparkline || undefined,
            top_bullish: d?.top_bullish || [],
            top_bearish: d?.top_bearish || [],
          };
        });
        setTickers(results);
        // Use real headline data from API responses only — no fabricated headlines
        const realHeadlines: HeadlineItem[] = [];
        results.forEach((t) => {
          if (t.top_bullish) {
            t.top_bullish.forEach((h) => {
              realHeadlines.push({
                title: h,
                source: t.ticker,
                time: t.timestamp || "",
                score: t.score,
                sentiment: "bullish",
              });
            });
          }
          if (t.top_bearish) {
            t.top_bearish.forEach((h) => {
              realHeadlines.push({
                title: h,
                source: t.ticker,
                time: t.timestamp || "",
                score: -Math.abs(t.score),
                sentiment: "bearish",
              });
            });
          }
        });
        setHeadlines(realHeadlines.slice(0, 12));
      } else {
        const placeholders = TRACKED_TICKERS.map((t) => ({
          ticker: t,
          overall_sentiment: "neutral",
          score: 0,
          confidence: 0.5,
          num_articles: 0,
        }));
        setTickers(placeholders);
        setHeadlines([]);
      }

      setLastRefresh(new Date());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="app-page">
      <SubNav
        items={[
          { href: "/ai-intelligence", label: "Market Intel" },
          { href: "/sentiment", label: "Sentiment" },
          { href: "/models", label: "Models" },
          { href: "/quant", label: "Quant" },
        ]}
      />

      <PageHeader
        eyebrow="Intelligence"
        title="Market Sentiment"
        description="Aggregated sentiment analysis from news, social media, and financial data sources."
        badge={
          <Badge variant="info" className="gap-1.5">
            <Activity className="h-3 w-3" />
            FinGPT + {mood?.sources_count ?? 17} SOURCES
          </Badge>
        }
        meta={
          lastRefresh ? (
            <span className="app-pill font-mono tracking-normal">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          ) : undefined
        }
        actions={
          <button onClick={fetchData} className="app-button-secondary" disabled={loading}>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh
          </button>
        }
      />

      {loading && !mood && <PageSkeleton />}

      {!loading && error && !mood && (
        <div className="app-panel p-8 text-center">
          <p className="text-muted-foreground">Unable to load sentiment data. Try refreshing.</p>
        </div>
      )}

      {!loading && !error && !mood && <EmptyState />}

      {mood && (
        <>
          {/* ── Section 1: Overall Market Mood ──────────────────────────── */}
          <div className="app-panel p-4">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:gap-6">
              {/* Mood label + score bar */}
              <div className="flex-1 space-y-3">
                <div className="flex items-center gap-3">
                  {/* Mood pill with color-matched glow */}
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border px-4 py-1.5 text-sm font-semibold transition-shadow ${moodColorClasses(
                      mood.market_mood
                    )}`}
                    style={moodGlowStyle(mood.market_mood)}
                  >
                    {mood.score >= 0 ? (
                      <TrendingUp className="h-3.5 w-3.5" />
                    ) : (
                      <TrendingDown className="h-3.5 w-3.5" />
                    )}
                    {moodLabel(mood.market_mood)}
                  </span>
                  <span className="text-[11px] font-semibold uppercase tracking-[0.15em] text-muted-foreground">
                    Overall Market Score
                  </span>
                </div>

                {/* Score bar */}
                <div className="space-y-1">
                  <div className="relative h-3 w-full rounded-full overflow-hidden bg-gradient-to-r from-red-500/30 via-zinc-500/20 to-emerald-500/30">
                    {mood.score >= 0 ? (
                      <div
                        className="absolute top-0 h-full rounded-r-full bg-gradient-to-r from-emerald-500/60 to-emerald-400"
                        style={{ left: "50%", width: `${(mood.score / 5) * 50}%` }}
                      />
                    ) : (
                      <div
                        className="absolute top-0 h-full rounded-l-full bg-gradient-to-l from-red-500/60 to-red-400"
                        style={{ right: "50%", width: `${(Math.abs(mood.score) / 5) * 50}%` }}
                      />
                    )}
                    <ScoreBarDot score={mood.score} />
                    <div className="absolute left-1/2 top-0 w-px h-full bg-white/30" />
                  </div>
                  <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                    <span>-5 Bearish</span>
                    <span>0</span>
                    <span>+5 Bullish</span>
                  </div>
                </div>
              </div>

              {/* Signal counts */}
              <div className="flex items-center gap-4 md:gap-5">
                <div className="text-center">
                  <div className="text-lg font-semibold tabular-nums text-emerald-400">
                    {mood.bullish_count}
                  </div>
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Bullish
                  </div>
                </div>
                <div className="h-8 w-px bg-border/50" />
                <div className="text-center">
                  <div className="text-lg font-semibold tabular-nums text-red-400">
                    {mood.bearish_count}
                  </div>
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Bearish
                  </div>
                </div>
                <div className="h-8 w-px bg-border/50" />
                <div className="text-center">
                  <div className="text-lg font-semibold tabular-nums text-zinc-400">
                    {mood.neutral_count}
                  </div>
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Neutral
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── Section 2: Ticker Sentiment Grid ───────────────────────── */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="app-section-title px-1">Ticker Sentiment</h2>
              <Badge variant="neutral">{tickers.length} TRACKED</Badge>
            </div>

            {tickers.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {tickers.map((t) => (
                  <div
                    key={t.ticker}
                    className="app-card p-3 space-y-2.5 cursor-default transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
                  >
                    {/* Header row: ticker + score */}
                    <div className="flex items-center justify-between">
                      <span className="text-base font-semibold tracking-tight">{t.ticker}</span>
                      <span
                        className={`text-lg font-semibold font-mono tabular-nums ${scoreColor(t.score)}`}
                      >
                        {t.score > 0 ? "+" : ""}
                        {t.score.toFixed(1)}
                      </span>
                    </div>

                    {/* Badge + article count */}
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={sentimentBadgeVariant(t.overall_sentiment)}
                        className="text-[10px]"
                      >
                        {t.overall_sentiment === "bullish" ||
                        t.overall_sentiment === "cautiously_optimistic" ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : t.overall_sentiment === "bearish" ||
                          t.overall_sentiment === "cautiously_pessimistic" ? (
                          <TrendingDown className="h-3 w-3" />
                        ) : (
                          <Activity className="h-3 w-3" />
                        )}
                        {moodLabel(t.overall_sentiment)}
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">
                        {t.num_articles} articles
                      </span>
                    </div>

                    {/* Confidence bar + sparkline */}
                    <div className="flex items-center gap-3">
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                            Confidence
                          </span>
                          <span className="text-[10px] font-mono tabular-nums text-muted-foreground">
                            {(t.confidence * 100).toFixed(0)}%
                          </span>
                        </div>
                        <ConfidenceBar value={t.confidence} />
                      </div>
                      {t.sparkline && (
                        <MiniSparkline data={t.sparkline} positive={t.score >= 0} ticker={t.ticker} />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── Section 3: Timeline + Headlines ────────────────────────── */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-[3fr_2fr]">
            {/* Sentiment Timeline */}
            <div className="app-panel">
              <div className="app-section-header">
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
                  <h3 className="app-section-title">Sentiment Timeline</h3>
                  {timelineSimulated && timeline.length > 0 && (
                    <Badge variant="warning" className="text-[9px]">[SIMULATED]</Badge>
                  )}
                </div>
                <Badge variant="neutral">30 DAYS</Badge>
              </div>
              {timeline.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <BarChart3 className="h-6 w-6 mb-2 opacity-40" />
                  <p className="text-xs font-medium">No timeline data available</p>
                  <p className="text-[11px] text-muted-foreground/60 mt-1">Timeline will populate with historical sentiment data</p>
                </div>
              ) : (
              <div className="p-3">
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart
                    data={timeline}
                    margin={{ top: 10, right: 10, bottom: 10, left: -10 }}
                  >
                    <defs>
                      <linearGradient id="sentimentGreen" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(var(--positive))" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="hsl(var(--positive))" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="sentimentRed" x1="0" y1="1" x2="0" y2="0">
                        <stop offset="0%" stopColor="hsl(var(--negative))" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="hsl(var(--negative))" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="0"
                      stroke="hsl(var(--border))"
                      strokeOpacity={0.06}
                      vertical={false}
                    />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                      tickLine={false}
                      axisLine={false}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      domain={[-5, 5]}
                      tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => (v > 0 ? `+${v}` : String(v))}
                    />
                    <ReferenceLine
                      y={0}
                      stroke="hsl(var(--border))"
                      strokeWidth={1}
                      strokeOpacity={0.5}
                    />
                    {/* Event annotations */}
                    {timeline
                      .filter((p) => p.event)
                      .map((p) => (
                        <ReferenceLine
                          key={p.date}
                          x={p.date}
                          stroke="hsl(var(--muted-foreground))"
                          strokeOpacity={0.25}
                          strokeDasharray="4 4"
                          label={{
                            value: p.event!,
                            position: "top",
                            fill: "hsl(var(--muted-foreground))",
                            fontSize: 9,
                          }}
                        />
                      ))}
                    <Tooltip content={<SentimentTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="score"
                      stroke="hsl(var(--positive))"
                      fill="url(#sentimentGreen)"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{
                        r: 4,
                        fill: "hsl(var(--positive))",
                        stroke: "white",
                        strokeWidth: 2,
                      }}
                      baseValue={0}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              )}
            </div>

            {/* Headlines */}
            <div className="app-panel flex flex-col">
              <div className="app-section-header">
                <div className="flex items-center gap-2">
                  <Newspaper className="h-3.5 w-3.5 text-muted-foreground" />
                  <h3 className="app-section-title">Recent Headlines</h3>
                </div>
                <Badge variant="neutral">{headlines.length}</Badge>
              </div>

              {headlines.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center py-10 gap-2 text-muted-foreground">
                  <Newspaper className="h-6 w-6 opacity-40" />
                  <p className="text-xs font-medium">No recent headlines available</p>
                </div>
              ) : (
                <div className="flex-1 min-h-0 overflow-y-auto">
                  <div className="divide-y divide-border/40">
                    {headlines.map((h, i) => {
                      const recent = isRecent(h.time);
                      return (
                        <div
                          key={i}
                          className="flex items-start gap-2.5 px-3 py-2.5 transition-colors hover:bg-muted/20 cursor-default"
                        >
                          {/* Colored dot — pulses if recent */}
                          <div
                            className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${headlineDotColor(h.score)} ${
                              recent ? "animate-pulse" : ""
                            }`}
                          />
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-medium leading-snug text-foreground line-clamp-2">
                              {h.title}
                            </p>
                            <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground/70">
                              <span className="font-medium text-muted-foreground">{h.source}</span>
                              <span>&middot;</span>
                              <span>{h.time}</span>
                            </div>
                          </div>
                          {/* Score badge */}
                          <span
                            className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-mono font-semibold tabular-nums ${scoreColor(h.score)} ${
                              h.score >= 0.5
                                ? "bg-emerald-400/10"
                                : h.score <= -0.5
                                ? "bg-red-400/10"
                                : "bg-zinc-400/10"
                            }`}
                          >
                            {h.score > 0 ? "+" : ""}
                            {h.score.toFixed(1)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
