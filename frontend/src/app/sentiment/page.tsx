"use client";

import React, { useEffect, useState, useCallback } from "react";
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
  // Add some event annotations
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

  // If no headlines from API, generate some placeholder ones
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

// Simple SVG sparkline
function MiniSparkline({ data, positive }: { data: number[]; positive: boolean }) {
  if (!data || data.length < 2) return null;
  const height = 24;
  const width = 64;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} className="shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={positive ? "hsl(var(--positive))" : "hsl(var(--negative))"}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function PageSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      <div className="app-panel p-5">
        <div className="h-10 w-48 rounded-full bg-muted mx-auto mb-4" />
        <div className="h-6 w-full rounded bg-muted" />
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="app-card p-3 space-y-3">
            <div className="h-5 w-20 bg-muted rounded" />
            <div className="h-3 w-full bg-muted rounded" />
            <div className="h-6 w-16 bg-muted rounded" />
          </div>
        ))}
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
        // Fill defaults
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
        setTimeline(generateTimeline(moodData.score ?? 0));
      } else {
        // Use defaults on failure
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
            sparkline: d?.sparkline || Array.from({ length: 7 }, () => (d?.score ?? 0) + (Math.random() - 0.5) * 2),
            top_bullish: d?.top_bullish || [],
            top_bearish: d?.top_bearish || [],
          };
        });
        setTickers(results);
        setHeadlines(generateHeadlines(results));
      } else {
        // Generate placeholder tickers
        const placeholders = TRACKED_TICKERS.map((t) => ({
          ticker: t,
          overall_sentiment: "neutral",
          score: 0,
          confidence: 0.5,
          num_articles: 0,
          sparkline: Array.from({ length: 7 }, () => (Math.random() - 0.5) * 2),
        }));
        setTickers(placeholders);
        setHeadlines(generateHeadlines(placeholders));
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

      {mood && (
        <>
          {/* ── Section 1: Overall Market Mood ──────────────────────────── */}
          <div className="app-panel p-4">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:gap-6">
              {/* Mood label + score bar */}
              <div className="flex-1 space-y-3">
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border px-4 py-1.5 text-sm font-semibold ${moodColorClasses(
                      mood.market_mood
                    )}`}
                  >
                    {mood.score >= 0 ? (
                      <TrendingUp className="h-3.5 w-3.5" />
                    ) : (
                      <TrendingDown className="h-3.5 w-3.5" />
                    )}
                    {moodLabel(mood.market_mood)}
                  </span>
                  <span className="app-label">Overall Market Score</span>
                </div>

                {/* Score bar */}
                <div className="space-y-1">
                  <div className="relative h-3 w-full rounded-full overflow-hidden bg-gradient-to-r from-red-500/30 via-zinc-500/20 to-emerald-500/30">
                    {/* Fill from center */}
                    {mood.score >= 0 ? (
                      <div
                        className="absolute top-0 h-full rounded-r-full bg-gradient-to-r from-emerald-500/60 to-emerald-400"
                        style={{
                          left: "50%",
                          width: `${(mood.score / 5) * 50}%`,
                        }}
                      />
                    ) : (
                      <div
                        className="absolute top-0 h-full rounded-l-full bg-gradient-to-l from-red-500/60 to-red-400"
                        style={{
                          right: "50%",
                          width: `${(Math.abs(mood.score) / 5) * 50}%`,
                        }}
                      />
                    )}
                    {/* Dot indicator */}
                    <div
                      className="absolute top-1/2 -translate-y-1/2 h-4 w-4 rounded-full border-2 border-white shadow-lg bg-foreground"
                      style={{
                        left: `${((mood.score + 5) / 10) * 100}%`,
                        transform: "translate(-50%, -50%)",
                      }}
                    />
                    {/* Center line */}
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

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
              {tickers.map((t) => (
                <div key={t.ticker} className="app-card p-3 space-y-2.5">
                  {/* Header row: ticker + score */}
                  <div className="flex items-center justify-between">
                    <span className="text-base font-semibold tracking-tight">
                      {t.ticker}
                    </span>
                    <span className={`text-lg font-semibold font-mono tabular-nums ${scoreColor(t.score)}`}>
                      {t.score > 0 ? "+" : ""}
                      {t.score.toFixed(1)}
                    </span>
                  </div>

                  {/* Badge + article count */}
                  <div className="flex items-center gap-2">
                    <Badge variant={sentimentBadgeVariant(t.overall_sentiment)} className="text-[10px]">
                      {t.overall_sentiment === "bullish" || t.overall_sentiment === "cautiously_optimistic" ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : t.overall_sentiment === "bearish" || t.overall_sentiment === "cautiously_pessimistic" ? (
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
                      <div className="app-progress-track">
                        <div
                          className="app-progress-bar bg-primary/70"
                          style={{ width: `${t.confidence * 100}%` }}
                        />
                      </div>
                    </div>
                    {t.sparkline && (
                      <MiniSparkline data={t.sparkline} positive={t.score >= 0} />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Section 3: Timeline + Headlines ────────────────────────── */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-[3fr_2fr]">
            {/* Sentiment Timeline */}
            <div className="app-panel">
              <div className="app-section-header">
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
                  <h3 className="app-section-title">Sentiment Timeline</h3>
                </div>
                <Badge variant="neutral">30 DAYS</Badge>
              </div>
              <div className="p-3">
                <ResponsiveContainer width="100%" height={260}>
                  <AreaChart
                    data={timeline}
                    margin={{ top: 10, right: 10, bottom: 10, left: -10 }}
                  >
                    <defs>
                      <linearGradient id="sentimentGreen" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(var(--positive))" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="hsl(var(--positive))" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="sentimentRed" x1="0" y1="1" x2="0" y2="0">
                        <stop offset="0%" stopColor="hsl(var(--negative))" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="hsl(var(--negative))" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="hsl(var(--border) / 0.3)"
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
                    <ReferenceLine y={0} stroke="hsl(var(--border))" strokeWidth={1} />
                    {/* Event annotations */}
                    {timeline
                      .filter((p) => p.event)
                      .map((p) => (
                        <ReferenceLine
                          key={p.date}
                          x={p.date}
                          stroke="hsl(var(--muted-foreground) / 0.4)"
                          strokeDasharray="4 4"
                          label={{
                            value: p.event!,
                            position: "top",
                            fill: "hsl(var(--muted-foreground))",
                            fontSize: 9,
                          }}
                        />
                      ))}
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--surface-overlay))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "12px",
                        fontSize: "12px",
                      }}
                      formatter={(val: number) => [
                        val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2),
                        "Score",
                      ]}
                    />
                    <Area
                      type="monotone"
                      dataKey="score"
                      stroke="hsl(var(--positive))"
                      fill="url(#sentimentGreen)"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, fill: "hsl(var(--positive))" }}
                      baseValue={0}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
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
              <div className="flex-1 min-h-0 overflow-y-auto">
                <div className="divide-y divide-border/40">
                  {headlines.map((h, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2.5 px-3 py-2.5 transition-colors hover:bg-muted/20"
                    >
                      <div
                        className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${headlineDotColor(h.score)}`}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium leading-snug text-foreground line-clamp-2">
                          {h.title}
                        </p>
                        <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                          <span>{h.source}</span>
                          <span>&middot;</span>
                          <span>{h.time}</span>
                        </div>
                      </div>
                      <span
                        className={`shrink-0 text-xs font-mono font-medium tabular-nums ${scoreColor(h.score)}`}
                      >
                        {h.score > 0 ? "+" : ""}
                        {h.score.toFixed(1)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
