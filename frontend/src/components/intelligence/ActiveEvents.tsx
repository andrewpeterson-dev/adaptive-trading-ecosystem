"use client";

import { useEffect, useState } from "react";
import { Zap } from "lucide-react";
import { getMarketEvents, type MarketEvent } from "@/lib/reasoning-api";
import { usePolling } from "@/hooks/usePolling";

const IMPACT_STYLES: Record<string, string> = {
  HIGH: "border-rose-400/25 bg-rose-400/10 text-rose-400",
  MEDIUM: "border-amber-400/25 bg-amber-400/10 text-amber-400",
  LOW: "border-border/60 bg-muted/10 text-muted-foreground",
};

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

export function ActiveEvents() {
  const [filter, setFilter] = useState<string | null>(null);
  const { data, loading, error, refresh } = usePolling<MarketEvent[]>({
    fetcher: () => getMarketEvents({ impact: filter ?? undefined, limit: 50 }),
    interval: 30_000,
  });
  const events = data ?? [];

  useEffect(() => {
    refresh();
  }, [filter, refresh]);

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          <Zap className="h-3.5 w-3.5 text-amber-400" />
          Active Market Events
        </div>
        <div className="flex gap-1.5">
          {[null, "HIGH", "MEDIUM", "LOW"].map((level) => (
            <button
              key={level ?? "all"}
              onClick={() => setFilter(level)}
              className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] transition-colors ${
                filter === level
                  ? "border border-primary/20 bg-primary/12 text-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {level ?? "All"}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 max-h-[480px] space-y-2 overflow-y-auto">
        {loading ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-6 text-center text-sm text-muted-foreground">
            Loading market events…
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-rose-400/20 bg-rose-400/5 px-4 py-6 text-center text-sm text-rose-300">
            Market events unavailable. {error}
          </div>
        ) : events.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 bg-muted/5 px-4 py-6 text-center space-y-2">
            <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-amber-400/5 border border-dashed border-amber-400/20 mx-auto">
              <Zap className="h-4 w-4 text-amber-400/40" />
            </div>
            <p className="text-sm text-slate-400 max-w-xs mx-auto leading-relaxed">
              Market events (FOMC announcements, earnings surprises, sector moves) will appear here as they are detected during trading hours.
            </p>
          </div>
        ) : (
          events.map((evt) => (
            <div
              key={evt.id}
              className={`rounded-2xl border px-4 py-3 ${IMPACT_STYLES[evt.impact] ?? IMPACT_STYLES.LOW}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-current/20 bg-current/8 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.16em]">
                      {evt.impact}
                    </span>
                    <span className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
                      {evt.event_type}
                    </span>
                  </div>
                  <p className="mt-1.5 text-sm font-medium text-foreground leading-snug">
                    {evt.headline}
                  </p>
                  {evt.symbols.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {evt.symbols.slice(0, 5).map((s) => (
                        <span key={s} className="app-pill px-2 py-0.5 text-[10px] font-mono">
                          {s}
                        </span>
                      ))}
                      {evt.symbols.length > 5 && (
                        <span className="text-[10px] text-muted-foreground">
                          +{evt.symbols.length - 5} more
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-[10px] text-muted-foreground">{timeAgo(evt.detected_at)}</div>
                  <div className="mt-0.5 text-[10px] text-muted-foreground/60">{evt.source}</div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
