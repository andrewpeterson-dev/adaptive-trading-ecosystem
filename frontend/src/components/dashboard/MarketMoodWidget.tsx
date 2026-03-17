"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { TrendingUp, TrendingDown, ArrowRight } from "lucide-react";
import { apiFetch } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MoodOverview {
  market_mood: string;
  score: number;
  confidence: number;
  bullish_count: number;
  bearish_count: number;
  neutral_count: number;
}

interface TickerMini {
  ticker: string;
  score: number;
  sentiment: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
      return { boxShadow: "0 0 12px rgba(52,211,153,0.3), 0 0 4px rgba(52,211,153,0.15)" };
    case "cautiously_optimistic":
      return { boxShadow: "0 0 10px rgba(110,231,183,0.22)" };
    case "mixed":
    case "neutral":
      return { boxShadow: "0 0 10px rgba(251,191,36,0.2)" };
    case "cautiously_pessimistic":
      return { boxShadow: "0 0 10px rgba(251,146,60,0.22)" };
    case "bearish":
      return { boxShadow: "0 0 12px rgba(248,113,113,0.3), 0 0 4px rgba(248,113,113,0.15)" };
    default:
      return {};
  }
}

function scoreColor(score: number): string {
  if (score >= 0.5) return "text-emerald-400";
  if (score > -0.5) return "text-zinc-400";
  return "text-red-400";
}

// ---------------------------------------------------------------------------
// Animated score bar dot
// ---------------------------------------------------------------------------

function ScoreBarDot({ score, size = 3 }: { score: number; size?: number }) {
  const [mounted, setMounted] = useState(false);
  const targetLeft = `${((score + 5) / 10) * 100}%`;

  useEffect(() => {
    const frame = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const px = size === 3 ? "h-3 w-3" : "h-2.5 w-2.5";

  return (
    <div
      className={`absolute top-1/2 ${px} rounded-full border-2 border-white bg-foreground`}
      style={{
        left: mounted ? targetLeft : "50%",
        transform: "translate(-50%, -50%)",
        transition: "left 700ms cubic-bezier(0.34, 1.56, 0.64, 1)",
        boxShadow: "0 1px 6px rgba(0,0,0,0.25), 0 0 0 1.5px rgba(255,255,255,0.12)",
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// Widget Component
// ---------------------------------------------------------------------------

export function MarketMoodWidget() {
  const [mood, setMood] = useState<MoodOverview | null>(null);
  const [topTickers, setTopTickers] = useState<TickerMini[]>([]);
  const [loading, setLoading] = useState(true);
  const [hovered, setHovered] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [moodRes, batchRes] = await Promise.allSettled([
        apiFetch<MoodOverview>("/api/sentiment/market-mood/overview"),
        apiFetch<Record<string, any>>(
          "/api/sentiment/batch/analyze?tickers=SPY,QQQ,NVDA"
        ),
      ]);

      if (moodRes.status === "fulfilled") {
        setMood({
          market_mood: moodRes.value.market_mood || "neutral",
          score: moodRes.value.score ?? 0,
          confidence: moodRes.value.confidence ?? 0.5,
          bullish_count: moodRes.value.bullish_count ?? 0,
          bearish_count: moodRes.value.bearish_count ?? 0,
          neutral_count: moodRes.value.neutral_count ?? 0,
        });
      }

      if (batchRes.status === "fulfilled") {
        const data = batchRes.value;
        const tickers: TickerMini[] = ["SPY", "QQQ", "NVDA"].map((t) => {
          const d = (data as any)[t] || {};
          return {
            ticker: t,
            score: d?.score ?? 0,
            sentiment: d?.overall_sentiment || d?.sentiment || "neutral",
          };
        });
        setTopTickers(tickers);
      }
    } catch {
      // Silently fail — widget is non-critical
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="space-y-3 p-1">
        {/* Pill skeleton */}
        <div className="flex justify-center">
          <div className="h-7 w-32 app-skeleton rounded-full" />
        </div>
        {/* Bar skeleton */}
        <div className="h-2.5 w-full app-skeleton rounded-full" />
        {/* Ticker rows skeleton */}
        <div className="space-y-2 pt-0.5">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-2">
              <div className="h-4 w-10 app-skeleton rounded" />
              <div className="h-1.5 flex-1 app-skeleton rounded-full" />
              <div className="h-4 w-8 app-skeleton rounded" />
            </div>
          ))}
        </div>
        {/* Link skeleton */}
        <div className="h-4 w-32 app-skeleton rounded mx-auto" />
      </div>
    );
  }

  if (!mood) {
    return (
      <div className="flex items-center justify-center py-6 text-xs text-muted-foreground">
        No sentiment data
      </div>
    );
  }

  return (
    <div
      className="space-y-3 p-1 rounded-xl transition-all duration-300"
      style={
        hovered
          ? { boxShadow: "0 0 0 1px hsl(var(--ring) / 0.25), 0 0 16px hsl(var(--ring) / 0.1)" }
          : {}
      }
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Mood pill */}
      <div className="flex items-center justify-center">
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-semibold transition-shadow ${moodColorClasses(
            mood.market_mood
          )}`}
          style={moodGlowStyle(mood.market_mood)}
        >
          {mood.score >= 0 ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          {moodLabel(mood.market_mood)}
        </span>
      </div>

      {/* Compact score bar */}
      <div className="space-y-1">
        <div className="relative h-2 w-full rounded-full overflow-hidden bg-gradient-to-r from-red-500/25 via-zinc-500/15 to-emerald-500/25">
          {mood.score >= 0 ? (
            <div
              className="absolute top-0 h-full rounded-r-full bg-gradient-to-r from-emerald-500/50 to-emerald-400/70"
              style={{ left: "50%", width: `${(mood.score / 5) * 50}%` }}
            />
          ) : (
            <div
              className="absolute top-0 h-full rounded-l-full bg-gradient-to-l from-red-500/50 to-red-400/70"
              style={{ right: "50%", width: `${(Math.abs(mood.score) / 5) * 50}%` }}
            />
          )}
          <ScoreBarDot score={mood.score} size={3} />
          <div className="absolute left-1/2 top-0 w-px h-full bg-white/20" />
        </div>
        <div className="flex justify-between text-[9px] font-mono text-muted-foreground">
          <span>-5</span>
          <span className="font-semibold tabular-nums">
            {mood.score > 0 ? "+" : ""}
            {mood.score.toFixed(1)}
          </span>
          <span>+5</span>
        </div>
      </div>

      {/* Top 3 tickers */}
      <div className="space-y-1.5">
        {topTickers.map((t) => (
          <div key={t.ticker} className="flex items-center justify-between gap-2">
            <span className="text-xs font-mono font-medium w-10 text-foreground">{t.ticker}</span>
            <div className="flex-1 h-1.5 rounded-full overflow-hidden relative"
              style={{ background: "hsl(var(--muted) / 0.5)" }}
            >
              <div className="absolute left-1/2 top-0 w-px h-full bg-white/15" />
              {t.score >= 0 ? (
                <div
                  className="absolute top-0 h-full rounded-r-full bg-emerald-400/55"
                  style={{ left: "50%", width: `${(t.score / 5) * 50}%` }}
                />
              ) : (
                <div
                  className="absolute top-0 h-full rounded-l-full bg-red-400/55"
                  style={{ right: "50%", width: `${(Math.abs(t.score) / 5) * 50}%` }}
                />
              )}
            </div>
            <span
              className={`text-[10px] font-mono font-medium tabular-nums w-8 text-right ${scoreColor(t.score)}`}
            >
              {t.score > 0 ? "+" : ""}
              {t.score.toFixed(1)}
            </span>
          </div>
        ))}
      </div>

      {/* Link to full page — arrow animates on hover */}
      <Link
        href="/sentiment"
        className="group flex items-center justify-center gap-1 text-[10px] font-medium text-primary hover:text-primary/80 pt-1 transition-colors"
      >
        View Details
        <ArrowRight className="h-3 w-3 transition-transform duration-200 group-hover:translate-x-0.5" />
      </Link>
    </div>
  );
}
