"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  TrendingUp,
  TrendingDown,
  ExternalLink,
} from "lucide-react";
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

function scoreColor(score: number): string {
  if (score >= 0.5) return "text-emerald-400";
  if (score > -0.5) return "text-zinc-400";
  return "text-red-400";
}

// ---------------------------------------------------------------------------
// Widget Component
// ---------------------------------------------------------------------------

export function MarketMoodWidget() {
  const [mood, setMood] = useState<MoodOverview | null>(null);
  const [topTickers, setTopTickers] = useState<TickerMini[]>([]);
  const [loading, setLoading] = useState(true);

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
      // Silently fail - widget is non-critical
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
      <div className="space-y-3 animate-pulse p-1">
        <div className="h-7 w-32 rounded-full bg-muted mx-auto" />
        <div className="h-3 w-full rounded bg-muted" />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-5 bg-muted rounded" />
          ))}
        </div>
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
    <div className="space-y-3 p-1">
      {/* Mood pill */}
      <div className="flex items-center justify-center">
        <span
          className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-semibold ${moodColorClasses(
            mood.market_mood
          )}`}
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
              className="absolute top-0 h-full rounded-r-full bg-emerald-400/60"
              style={{
                left: "50%",
                width: `${(mood.score / 5) * 50}%`,
              }}
            />
          ) : (
            <div
              className="absolute top-0 h-full rounded-l-full bg-red-400/60"
              style={{
                right: "50%",
                width: `${(Math.abs(mood.score) / 5) * 50}%`,
              }}
            />
          )}
          <div
            className="absolute top-1/2 -translate-y-1/2 h-3 w-3 rounded-full border-2 border-white shadow bg-foreground"
            style={{
              left: `${((mood.score + 5) / 10) * 100}%`,
              transform: "translate(-50%, -50%)",
            }}
          />
          <div className="absolute left-1/2 top-0 w-px h-full bg-white/20" />
        </div>
        <div className="flex justify-between text-[9px] font-mono text-muted-foreground">
          <span>-5</span>
          <span className="font-semibold">
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
            <span className="text-xs font-mono font-medium w-10">{t.ticker}</span>
            <div className="flex-1 h-1.5 rounded-full bg-muted/40 overflow-hidden relative">
              <div className="absolute left-1/2 top-0 w-px h-full bg-white/15" />
              {t.score >= 0 ? (
                <div
                  className="absolute top-0 h-full rounded-r-full bg-emerald-400/50"
                  style={{ left: "50%", width: `${(t.score / 5) * 50}%` }}
                />
              ) : (
                <div
                  className="absolute top-0 h-full rounded-l-full bg-red-400/50"
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

      {/* Link to full page */}
      <Link
        href="/sentiment"
        className="flex items-center justify-center gap-1 text-[10px] font-medium text-primary hover:underline pt-1"
      >
        Full Sentiment Analysis
        <ExternalLink className="h-2.5 w-2.5" />
      </Link>
    </div>
  );
}
