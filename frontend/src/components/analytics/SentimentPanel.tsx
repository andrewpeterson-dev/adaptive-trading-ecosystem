"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Newspaper, Loader2 } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { SentimentReport } from "@/types/sentiment";

const MOOD_COLORS: Record<string, string> = {
  bullish: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
  cautiously_optimistic: "text-emerald-300 bg-emerald-300/10 border-emerald-300/30",
  mixed: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  neutral: "text-zinc-400 bg-zinc-400/10 border-zinc-400/30",
  cautiously_pessimistic: "text-orange-400 bg-orange-400/10 border-orange-400/30",
  bearish: "text-red-400 bg-red-400/10 border-red-400/30",
};

function moodLabel(mood: string | null | undefined): string {
  if (!mood) return "Neutral";
  return mood.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function scoreColor(score: number): string {
  if (score >= 2) return "bg-emerald-500";
  if (score >= 0.5) return "bg-emerald-400/70";
  if (score > -0.5) return "bg-zinc-500";
  if (score > -2) return "bg-red-400/70";
  return "bg-red-500";
}

function relevanceDot(relevance: number): string {
  if (relevance >= 0.7) return "bg-white";
  if (relevance >= 0.4) return "bg-white/50";
  return "bg-white/25";
}

function SkeletonBlock() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-8 w-32 rounded-full bg-muted mx-auto" />
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-6 bg-muted rounded" />
        ))}
      </div>
      <div className="h-4 w-48 bg-muted rounded mx-auto" />
    </div>
  );
}

export function SentimentPanel() {
  const [report, setReport] = useState<SentimentReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchReport = useCallback(async () => {
    try {
      const data = await apiFetch<SentimentReport>("/api/news/sentiment/report");
      setReport(data);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReport();
    const interval = setInterval(fetchReport, 60000);
    return () => clearInterval(interval);
  }, [fetchReport]);

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4 space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
        <Newspaper className="h-4 w-4" />
        Market Sentiment
      </div>

      {loading && <SkeletonBlock />}

      {!loading && error && (
        <div className="py-6 text-center text-muted-foreground text-sm">
          Unable to load sentiment data
        </div>
      )}

      {!loading && !error && !report && (
        <div className="py-6 text-center text-muted-foreground text-sm">
          No sentiment data available
        </div>
      )}

      {!loading && !error && report && (
        <>
          {/* Mood Badge */}
          <div className="flex justify-center">
            <span
              className={`text-sm font-semibold px-4 py-1.5 rounded-full border ${
                MOOD_COLORS[report.market_mood ?? ""] ?? MOOD_COLORS.neutral
              }`}
            >
              {moodLabel(report.market_mood)}
            </span>
          </div>

          {/* Per-Ticker Sentiment */}
          <div className="space-y-2">
            {Object.entries(report.ticker_sentiments ?? {}).map(([ticker, data]) => {
              const pctPos = ((data.score + 5) / 10) * 100;
              return (
                <div key={ticker} className="flex items-center gap-2">
                  <span className="w-12 text-xs font-mono font-medium text-right shrink-0">
                    {ticker}
                  </span>
                  <div
                    className="h-2 flex-1 rounded-full bg-muted overflow-hidden relative"
                    title={`Score: ${data.score.toFixed(1)}`}
                  >
                    {/* Center marker */}
                    <div className="absolute left-1/2 top-0 w-px h-full bg-white/20" />
                    {/* Score bar from center */}
                    {data.score >= 0 ? (
                      <div
                        className={`absolute top-0 h-full rounded-r-full ${scoreColor(data.score)}`}
                        style={{
                          left: "50%",
                          width: `${(data.score / 5) * 50}%`,
                        }}
                      />
                    ) : (
                      <div
                        className={`absolute top-0 h-full rounded-l-full ${scoreColor(data.score)}`}
                        style={{
                          right: "50%",
                          width: `${(Math.abs(data.score) / 5) * 50}%`,
                        }}
                      />
                    )}
                  </div>
                  <div
                    className={`h-2 w-2 rounded-full shrink-0 ${relevanceDot(data.relevance)}`}
                    title={`Relevance: ${(data.relevance * 100).toFixed(0)}%`}
                  />
                  <span className="w-8 text-[10px] font-mono text-muted-foreground text-right tabular-nums">
                    {data.score > 0 ? "+" : ""}{data.score.toFixed(1)}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Footer */}
          <div className="flex justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/30">
            <span>{report.article_count} articles analyzed</span>
            <span>
              {new Date(report.report_time).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
