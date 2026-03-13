"use client";

import { useEffect, useState } from "react";
import { MessageCircle } from "lucide-react";
import { getMarketEvents, type MarketEvent } from "@/lib/reasoning-api";

interface TickerSentiment {
  symbol: string;
  sentiment: "bullish" | "bearish" | "neutral";
  score: number;
}

function parseSentimentEvents(events: MarketEvent[]): TickerSentiment[] {
  const sentiments: TickerSentiment[] = [];
  for (const evt of events) {
    if (!evt.source?.startsWith("stocktwits")) continue;
    // Headline format: "SYMBOL sentiment: bullish (score: 72)" or similar
    const symbolMatch = evt.headline.match(/^(\w+)\s+sentiment/i);
    const sentimentMatch = evt.headline.match(/sentiment:\s*(bullish|bearish|neutral)/i);
    const scoreMatch = evt.headline.match(/score:\s*(\d+)/i);
    if (symbolMatch) {
      sentiments.push({
        symbol: symbolMatch[1],
        sentiment: (sentimentMatch?.[1]?.toLowerCase() as "bullish" | "bearish" | "neutral") ?? "neutral",
        score: scoreMatch ? parseInt(scoreMatch[1]) : 50,
      });
    }
  }
  return sentiments;
}

const SENTIMENT_COLORS = {
  bullish: { bg: "bg-emerald-400/10", border: "border-emerald-400/20", text: "text-emerald-400" },
  bearish: { bg: "bg-rose-400/10", border: "border-rose-400/20", text: "text-rose-400" },
  neutral: { bg: "bg-slate-400/10", border: "border-slate-400/20", text: "text-slate-400" },
};

export function SentimentTicker() {
  const [sentiments, setSentiments] = useState<TickerSentiment[]>([]);

  useEffect(() => {
    const fetch = () =>
      getMarketEvents({ event_type: "SENTIMENT", limit: 50 })
        .then((events) => setSentiments(parseSentimentEvents(events)))
        .catch(() => {});
    fetch();
    const interval = setInterval(fetch, 30_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <MessageCircle className="h-3.5 w-3.5 text-cyan-400" />
        Social Sentiment
      </div>

      <div className="mt-4">
        {sentiments.length === 0 ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-8 text-center text-sm text-muted-foreground">
            No sentiment signals detected
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
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
