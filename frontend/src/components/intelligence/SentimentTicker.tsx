"use client";

import { MessageCircle } from "lucide-react";
import { getMarketEvents, type MarketEvent } from "@/lib/reasoning-api";
import { usePolling } from "@/hooks/usePolling";
import { Skeleton } from "@/components/ui/skeleton";

interface TickerSentiment {
  symbol: string;
  sentiment: "bullish" | "bearish" | "neutral";
  score: number;
}

function parseSentimentEvents(events: MarketEvent[]): TickerSentiment[] {
  const sentiments: TickerSentiment[] = [];
  for (const evt of events) {
    if (evt.event_type !== "sentiment" || evt.source !== "stocktwits") continue;
    const symbol = String(evt.symbols?.[0] ?? "").toUpperCase();
    const bullish = Number(evt.raw_data?.bullish ?? 0);
    const bearish = Number(evt.raw_data?.bearish ?? 0);
    const total = Number(evt.raw_data?.total ?? bullish + bearish);
    if (!symbol || total <= 0) continue;

    const bullishScore = Math.round((bullish / total) * 100);
    const isBullish = bullishScore >= 50;
    sentiments.push({
      symbol,
      sentiment: isBullish ? "bullish" : "bearish",
      score: isBullish ? bullishScore : 100 - bullishScore,
    });
  }
  return sentiments;
}

const SENTIMENT_COLORS = {
  bullish: { bg: "bg-emerald-400/10", border: "border-emerald-400/20", text: "text-emerald-400" },
  bearish: { bg: "bg-rose-400/10", border: "border-rose-400/20", text: "text-rose-400" },
  neutral: { bg: "bg-slate-400/10", border: "border-slate-400/20", text: "text-muted-foreground" },
};

export function SentimentTicker() {
  const { data, loading, error } = usePolling<MarketEvent[]>({
    fetcher: () => getMarketEvents({ event_type: "sentiment", limit: 50 }),
    interval: 30_000,
  });
  const sentiments = parseSentimentEvents(data ?? []);

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <MessageCircle className="h-3.5 w-3.5 text-cyan-400" />
        Social Sentiment
      </div>

      <div className="mt-4">
        {loading ? (
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-border/40 p-3 space-y-2 text-center">
                <Skeleton className="h-4 w-12 mx-auto" />
                <Skeleton className="h-3 w-14 mx-auto" />
                <Skeleton className="h-2.5 w-16 mx-auto" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-dashed border-border/60 bg-muted/5 px-4 py-6 text-center space-y-3">
            <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-cyan-400/5 border border-dashed border-cyan-400/20 mx-auto">
              <MessageCircle className="h-4 w-4 text-cyan-400/40" />
            </div>
            <p className="text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
              Sentiment data is temporarily unavailable. It updates every 2 minutes during market hours.
            </p>
          </div>
        ) : sentiments.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 bg-muted/5 px-4 py-6 text-center space-y-3">
            <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-cyan-400/5 border border-dashed border-cyan-400/20 mx-auto">
              <MessageCircle className="h-4 w-4 text-cyan-400/40" />
            </div>
            <p className="text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
              Market sentiment data updates every 2 minutes during market hours. Check back when markets are open.
            </p>
            <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-3 opacity-30 pointer-events-none pt-1">
              {[
                { symbol: "AAPL", sentiment: "bullish" as const, score: 72 },
                { symbol: "TSLA", sentiment: "bearish" as const, score: 61 },
                { symbol: "NVDA", sentiment: "bullish" as const, score: 84 },
              ].map((s) => {
                const colors = SENTIMENT_COLORS[s.sentiment];
                return (
                  <div key={s.symbol} className={`rounded-xl border ${colors.border} ${colors.bg} p-3 text-center`}>
                    <div className="font-mono text-sm font-semibold text-foreground">{s.symbol}</div>
                    <div className={`mt-1 text-xs font-semibold uppercase tracking-wider ${colors.text}`}>{s.sentiment}</div>
                    <div className="mt-1 text-[10px] font-mono text-muted-foreground">{s.score}% {s.sentiment === "bullish" ? "bull" : "bear"}</div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-3">
            {sentiments.map((s) => {
              const colors = SENTIMENT_COLORS[s.sentiment];
              return (
                <div
                  key={s.symbol}
                  className={`rounded-xl border ${colors.border} ${colors.bg} p-3 text-center transition-colors`}
                >
                  <div className="font-mono text-sm font-semibold text-foreground">
                    {s.symbol}
                  </div>
                  <div className={`mt-1 text-xs font-semibold uppercase tracking-wider ${colors.text}`}>
                    {s.sentiment}
                  </div>
                  <div className="mt-1 text-[10px] font-mono text-muted-foreground">
                    {s.score}% {s.sentiment === "bullish" ? "bull" : "bear"}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
