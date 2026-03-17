"use client";

import React from "react";
import {
  Newspaper,
  TrendingUp,
  TrendingDown,
  Brain,
  Zap,
  Clock,
  BarChart3,
  Activity,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  ReferenceArea,
} from "recharts";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";

// ---------------------------------------------------------------------------
// Mock data — no API calls
// ---------------------------------------------------------------------------

const MOOD_COLORS: Record<string, string> = {
  bullish: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
  cautiously_optimistic: "text-emerald-300 bg-emerald-300/10 border-emerald-300/30",
  cautiously_pessimistic: "text-orange-400 bg-orange-400/10 border-orange-400/30",
  mixed: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  neutral: "text-zinc-400 bg-zinc-400/10 border-zinc-400/30",
  bearish: "text-red-400 bg-red-400/10 border-red-400/30",
};

function moodLabel(mood: string): string {
  return mood.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const TICKERS = [
  {
    ticker: "SPY",
    score: 2.1,
    mood: "bullish",
    articles: 8,
    confidence: 87,
    history: [1.2, 1.5, 1.8, 1.6, 1.9, 2.0, 2.1],
  },
  {
    ticker: "NVDA",
    score: 1.8,
    mood: "bullish",
    articles: 12,
    confidence: 92,
    history: [0.8, 1.1, 1.4, 1.2, 1.5, 1.7, 1.8],
  },
  {
    ticker: "AAPL",
    score: 0.3,
    mood: "neutral",
    articles: 6,
    confidence: 71,
    history: [0.6, 0.2, -0.1, 0.4, 0.3, 0.1, 0.3],
  },
  {
    ticker: "TSLA",
    score: -1.2,
    mood: "cautiously_pessimistic",
    articles: 9,
    confidence: 78,
    history: [-0.4, -0.7, -0.9, -1.1, -0.8, -1.3, -1.2],
  },
  {
    ticker: "META",
    score: 1.5,
    mood: "cautiously_optimistic",
    articles: 5,
    confidence: 68,
    history: [0.5, 0.9, 1.2, 1.0, 1.4, 1.3, 1.5],
  },
  {
    ticker: "AMZN",
    score: -0.1,
    mood: "neutral",
    articles: 4,
    confidence: 65,
    history: [0.3, 0.1, -0.2, 0.0, -0.3, 0.1, -0.1],
  },
];

// 30-day timeline — oscillating with dip around day 15, recovery after
const TIMELINE_DATA = Array.from({ length: 30 }, (_, i) => {
  const day = i + 1;
  let score: number;
  if (day <= 10) {
    score = 1.2 + Math.sin(day * 0.6) * 0.5;
  } else if (day <= 18) {
    // Dip around Fed Meeting (day 15)
    score = 0.6 - Math.sin((day - 10) * 0.4) * 1.4;
  } else {
    // Recovery — NVDA earnings boost at day 22
    score = -0.2 + ((day - 18) / 12) * 2.7 + Math.sin(day * 0.8) * 0.3;
  }
  return { day: `D${day}`, score: parseFloat(score.toFixed(2)) };
});

const HEADLINES = [
  {
    title: "NVIDIA Reports Record Revenue, AI Demand Surges 120% YoY",
    source: "Reuters",
    ago: "2h ago",
    score: 3.2,
  },
  {
    title: "Fed Signals Potential Rate Cut in June, Markets Rally",
    source: "Bloomberg",
    ago: "4h ago",
    score: 2.1,
  },
  {
    title: "Tesla Recalls 200K Vehicles Over Autopilot Safety Concerns",
    source: "WSJ",
    ago: "6h ago",
    score: -2.4,
  },
  {
    title: "Apple Vision Pro Sales Fall Short of Analyst Expectations",
    source: "CNBC",
    ago: "8h ago",
    score: -1.1,
  },
  {
    title: "Meta AI Studio Opens to Third-Party Developers Worldwide",
    source: "TechCrunch",
    ago: "10h ago",
    score: 1.7,
  },
  {
    title: "Amazon Web Services Posts 23% Revenue Growth in Q1",
    source: "FT",
    ago: "12h ago",
    score: 0.8,
  },
  {
    title: "Inflation Data Misses Estimates, Treasury Yields Spike",
    source: "Bloomberg",
    ago: "14h ago",
    score: -1.8,
  },
  {
    title: "S&P 500 Hits New All-Time High as Tech Sector Leads Gains",
    source: "Reuters",
    ago: "16h ago",
    score: 2.5,
  },
];

// ---------------------------------------------------------------------------
// Helper sub-components
// ---------------------------------------------------------------------------

function ScoreDot({ score }: { score: number }) {
  let color = "bg-zinc-400";
  if (score >= 2) color = "bg-emerald-400";
  else if (score >= 0.5) color = "bg-emerald-300";
  else if (score > -0.5) color = "bg-zinc-400";
  else if (score > -2) color = "bg-orange-400";
  else color = "bg-red-400";
  return <span className={`inline-block h-2 w-2 rounded-full ${color} shrink-0`} />;
}

function ScoreBadge({ score }: { score: number }) {
  const sign = score >= 0 ? "+" : "";
  let cls = "text-zinc-400";
  if (score >= 2) cls = "text-emerald-400";
  else if (score >= 0.5) cls = "text-emerald-300";
  else if (score > -0.5) cls = "text-zinc-400";
  else if (score > -2) cls = "text-orange-400";
  else cls = "text-red-400";
  return (
    <span className={`font-mono text-sm font-semibold tabular-nums ${cls}`}>
      {sign}{score.toFixed(1)}
    </span>
  );
}

// Tiny inline SVG sparkline
function Sparkline({ data }: { data: number[] }) {
  const W = 72;
  const H = 24;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * W;
      const y = H - ((v - min) / range) * H;
      return `${x},${y}`;
    })
    .join(" ");
  const lastVal = data[data.length - 1];
  const isPositive = lastVal >= 0;
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="overflow-visible">
      <polyline
        points={pts}
        fill="none"
        stroke={isPositive ? "#34d399" : "#f87171"}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

// Confidence bar
function ConfidenceBar({ pct }: { pct: number }) {
  let color = "bg-zinc-500";
  if (pct >= 85) color = "bg-emerald-500";
  else if (pct >= 70) color = "bg-emerald-400/70";
  else if (pct >= 55) color = "bg-amber-400/70";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-mono text-muted-foreground tabular-nums w-7 text-right">
        {pct}%
      </span>
    </div>
  );
}

// Ticker sentiment card
function TickerCard({
  ticker,
  score,
  mood,
  articles,
  confidence,
  history,
}: (typeof TICKERS)[number]) {
  const moodCls = MOOD_COLORS[mood] ?? MOOD_COLORS.neutral;
  const accentBorder =
    mood === "bullish" || mood === "cautiously_optimistic"
      ? "border-l-emerald-500/50"
      : mood === "cautiously_pessimistic"
      ? "border-l-orange-500/50"
      : mood === "bearish"
      ? "border-l-red-500/50"
      : "border-l-zinc-500/30";

  return (
    <div
      className={`rounded-xl border border-border/60 bg-card shadow-sm p-4 space-y-3 border-l-2 ${accentBorder}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between">
        <div>
          <p className="text-lg font-bold tracking-tight text-foreground font-mono">{ticker}</p>
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${moodCls}`}>
            {moodLabel(mood)}
          </span>
        </div>
        <div className="text-right">
          <ScoreBadge score={score} />
          <p className="text-[10px] text-muted-foreground mt-0.5">{articles} articles</p>
        </div>
      </div>

      {/* Confidence */}
      <div className="space-y-1">
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Confidence</p>
        <ConfidenceBar pct={confidence} />
      </div>

      {/* Sparkline */}
      <div className="flex items-end justify-between">
        <p className="text-[10px] text-muted-foreground">7-day trend</p>
        <Sparkline data={history} />
      </div>
    </div>
  );
}

// Custom recharts tooltip
function TimelineTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  const val = payload[0].value;
  const sign = val >= 0 ? "+" : "";
  const color = val >= 1 ? "#34d399" : val >= 0 ? "#a3e635" : val > -1 ? "#fbbf24" : "#f87171";
  return (
    <div className="rounded-lg border border-border/60 bg-card px-3 py-2 text-xs shadow-lg">
      <p className="text-muted-foreground mb-0.5">{label}</p>
      <p className="font-mono font-semibold" style={{ color }}>
        {sign}{val.toFixed(2)}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SentimentPreviewPage() {
  const bullish = TICKERS.filter((t) => t.score > 1).length;
  const bearish = TICKERS.filter((t) => t.score < -0.5).length;
  const neutral = TICKERS.length - bullish - bearish;

  return (
    <div className="app-page space-y-6">
      {/* Page Header */}
      <PageHeader
        eyebrow="Intelligence"
        title="Market Sentiment"
        description="FinGPT-powered sentiment analysis across tickers, news sources, and market timeline."
        meta={
          <span className="app-pill font-mono tracking-normal">
            <Brain className="mr-1.5 inline h-3 w-3" />
            FinGPT + 17 sources
          </span>
        }
      />

      {/* ------------------------------------------------------------------ */}
      {/* Section 1 — Market Mood Overview                                   */}
      {/* ------------------------------------------------------------------ */}
      <div className="rounded-xl border border-border/60 bg-card shadow-sm p-6">
        <div className="flex flex-col gap-6 md:flex-row md:items-center">
          {/* Left: big mood indicator */}
          <div className="flex flex-col items-center gap-3 md:w-64 md:shrink-0">
            {/* Glow container */}
            <div className="relative flex items-center justify-center">
              <div className="absolute h-20 w-48 rounded-full bg-emerald-400/20 blur-2xl" />
              <span className="relative text-lg font-semibold text-emerald-300 border border-emerald-400/30 bg-emerald-400/10 px-5 py-2 rounded-full">
                Cautiously Optimistic
              </span>
            </div>
            {/* Powered-by pill */}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border/50 bg-muted/30 px-3 py-1 text-[11px] text-muted-foreground">
              <Zap className="h-3 w-3 text-amber-400" />
              FinGPT + 17 sources
            </span>
          </div>

          {/* Center: score gauge */}
          <div className="flex-1 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground uppercase tracking-wider">
                Overall Market Score
              </span>
              <span className="font-mono text-xl font-bold text-emerald-300">+1.4</span>
            </div>
            {/* Gauge bar: -5 to +5 */}
            <div className="relative h-3 rounded-full bg-gradient-to-r from-red-500/60 via-amber-400/40 via-50% to-emerald-500/60 overflow-hidden">
              {/* Center tick */}
              <div className="absolute left-1/2 top-0 h-full w-px bg-white/30" />
              {/* Indicator */}
              <div
                className="absolute top-0.5 h-2 w-2 rounded-full bg-emerald-300 shadow-sm shadow-emerald-400/60 ring-1 ring-white/20"
                style={{ left: `calc(${((1.4 + 5) / 10) * 100}% - 4px)` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground font-mono">
              <span>-5 Bearish</span>
              <span>0 Neutral</span>
              <span>+5 Bullish</span>
            </div>
          </div>

          {/* Right: mini metrics */}
          <div className="flex gap-4 md:flex-col md:gap-3 md:w-40 md:shrink-0">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400 shrink-0" />
              <div>
                <p className="text-[10px] text-muted-foreground">Bullish Signals</p>
                <p className="font-mono text-sm font-bold text-emerald-400">12</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-red-400 shrink-0" />
              <div>
                <p className="text-[10px] text-muted-foreground">Bearish Signals</p>
                <p className="font-mono text-sm font-bold text-red-400">4</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-zinc-400 shrink-0" />
              <div>
                <p className="text-[10px] text-muted-foreground">Neutral</p>
                <p className="font-mono text-sm font-bold text-zinc-400">6</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2 — Ticker Sentiment Grid                                  */}
      {/* ------------------------------------------------------------------ */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
          <BarChart3 className="h-4 w-4" />
          <span className="uppercase tracking-wider text-xs">Ticker Sentiment</span>
          <Badge variant="neutral" className="ml-auto text-[10px]">
            {TICKERS.length} tracked
          </Badge>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TICKERS.map((t) => (
            <TickerCard key={t.ticker} {...t} />
          ))}
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Section 3 + 4 — Timeline + Headlines (side by side on lg)          */}
      {/* ------------------------------------------------------------------ */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
        {/* Timeline */}
        <div className="rounded-xl border border-border/60 bg-card shadow-sm p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Sentiment Timeline
              </span>
            </div>
            <span className="text-[10px] text-muted-foreground">Last 30 days</span>
          </div>

          {/* Legend */}
          <div className="flex gap-4 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-3 rounded-sm bg-emerald-500/25" />
              Positive
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-3 rounded-sm bg-amber-400/20" />
              Caution
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-2 w-3 rounded-sm bg-red-500/20" />
              Negative
            </span>
          </div>

          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={TIMELINE_DATA}
                margin={{ top: 8, right: 12, left: -20, bottom: 0 }}
              >
                {/* Color bands */}
                <ReferenceArea y1={0} y2={3} fill="rgba(52,211,153,0.06)" />
                <ReferenceArea y1={-1} y2={0} fill="rgba(251,191,36,0.07)" />
                <ReferenceArea y1={-3} y2={-1} fill="rgba(248,113,113,0.08)" />

                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={false}
                  interval={4}
                />
                <YAxis
                  domain={[-2, 3]}
                  tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<TimelineTooltip />} />

                {/* Zero line */}
                <ReferenceLine y={0} stroke="hsl(var(--border))" strokeDasharray="3 3" />

                {/* Event annotations */}
                <ReferenceLine
                  x="D15"
                  stroke="hsl(var(--warning))"
                  strokeDasharray="4 3"
                  label={{
                    value: "Fed Meeting",
                    position: "top",
                    fontSize: 9,
                    fill: "hsl(var(--warning))",
                    offset: 4,
                  }}
                />
                <ReferenceLine
                  x="D22"
                  stroke="#34d399"
                  strokeDasharray="4 3"
                  label={{
                    value: "NVDA Earnings",
                    position: "top",
                    fontSize: 9,
                    fill: "#34d399",
                    offset: 4,
                  }}
                />

                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="#34d399"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 3, fill: "#34d399", strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Headlines */}
        <div className="rounded-xl border border-border/60 bg-card shadow-sm p-5 space-y-4">
          <div className="flex items-center gap-2">
            <Newspaper className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Recent Headlines
            </span>
          </div>

          <div className="space-y-1">
            {HEADLINES.map((h, i) => {
              const isPos = h.score > 0;
              const sign = isPos ? "+" : "";
              const scoreColor =
                h.score >= 2
                  ? "text-emerald-400"
                  : h.score >= 0.5
                  ? "text-emerald-300"
                  : h.score > -0.5
                  ? "text-zinc-400"
                  : h.score > -2
                  ? "text-orange-400"
                  : "text-red-400";

              return (
                <div
                  key={i}
                  className="flex items-start gap-3 py-2.5 border-b border-border/40 last:border-0"
                >
                  <ScoreDot score={h.score} />
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] leading-4 text-foreground/90 line-clamp-2">
                      {h.title}
                    </p>
                    <div className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                      <span>{h.source}</span>
                      <span>·</span>
                      <Clock className="h-2.5 w-2.5" />
                      <span>{h.ago}</span>
                    </div>
                  </div>
                  <span className={`font-mono text-[11px] font-semibold tabular-nums shrink-0 ${scoreColor}`}>
                    {sign}{h.score.toFixed(1)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
