"use client";

import { Newspaper } from "lucide-react";
import { getMarketEvents, type MarketEvent } from "@/lib/reasoning-api";
import { usePolling } from "@/hooks/usePolling";

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function NewsFeed() {
  const { data, loading, error } = usePolling<MarketEvent[]>({
    fetcher: () => getMarketEvents({ event_type: "news", limit: 15 }),
    interval: 30_000,
  });
  const news = data ?? [];

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <Newspaper className="h-3.5 w-3.5 text-blue-400" />
        Live News Feed
      </div>

      <div className="mt-4 max-h-[400px] space-y-2.5 overflow-y-auto">
        {loading ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-8 text-center text-sm text-muted-foreground">
            Loading news events…
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-rose-400/20 bg-rose-400/5 px-4 py-8 text-center text-sm text-rose-300">
            News feed unavailable. {error}
          </div>
        ) : news.length === 0 ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-8 text-center text-sm text-muted-foreground">
            No news events detected yet
          </div>
        ) : (
          news.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-border/40 bg-muted/5 px-3.5 py-2.5 transition-colors hover:bg-muted/10"
            >
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-medium leading-snug text-foreground">
                  {item.headline}
                </p>
                <span className="shrink-0 text-[10px] text-muted-foreground">
                  {timeAgo(item.detected_at)}
                </span>
              </div>
              {item.symbols.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {item.symbols.slice(0, 4).map((s) => (
                    <span
                      key={s}
                      className="rounded-md border border-blue-400/15 bg-blue-400/8 px-1.5 py-0.5 text-[10px] font-mono font-medium text-blue-400"
                    >
                      {s}
                    </span>
                  ))}
                  {item.symbols.length > 4 && (
                    <span className="text-[10px] text-muted-foreground">
                      +{item.symbols.length - 4}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
