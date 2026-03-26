"use client";

import { Calendar } from "lucide-react";
import { getMarketEvents, type MarketEvent } from "@/lib/reasoning-api";
import { usePolling } from "@/hooks/usePolling";
import { Skeleton } from "@/components/ui/skeleton";

const IMPACT_DOT = {
  HIGH: "bg-rose-400",
  MEDIUM: "bg-amber-400",
  LOW: "bg-slate-400",
};

export function EarningsCalendar() {
  const { data, loading, error } = usePolling<MarketEvent[]>({
    fetcher: () => getMarketEvents({ event_type: "earnings", limit: 20 }),
    interval: 60_000,
  });
  const events = data ?? [];

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <Calendar className="h-3.5 w-3.5 text-amber-400" />
        Upcoming Earnings
      </div>

      <div className="mt-4 max-h-[320px] space-y-2 overflow-y-auto">
        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 rounded-xl border border-border/40 px-3.5 py-2.5">
                <Skeleton className="h-2 w-2 shrink-0 rounded-full" />
                <div className="min-w-0 flex-1 space-y-1.5">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-2.5 w-16" />
                </div>
                <Skeleton className="h-3 w-12 shrink-0" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-dashed border-border/60 bg-muted/5 px-4 py-6 text-center space-y-3">
            <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-amber-400/5 border border-dashed border-amber-400/20 mx-auto">
              <Calendar className="h-4 w-4 text-amber-400/40" />
            </div>
            <p className="text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
              Earnings calendar is temporarily unavailable. Data refreshes automatically when the context monitor runs.
            </p>
          </div>
        ) : events.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/60 bg-muted/5 px-4 py-6 text-center space-y-3">
            <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-amber-400/5 border border-dashed border-amber-400/20 mx-auto">
              <Calendar className="h-4 w-4 text-amber-400/40" />
            </div>
            <p className="text-sm text-muted-foreground max-w-xs mx-auto leading-relaxed">
              No upcoming earnings events found. Earnings data refreshes automatically when the context monitor runs.
            </p>
            <div className="space-y-2 opacity-30 pointer-events-none pt-1">
              {[
                { symbol: "AAPL", headline: "Apple Inc. Q2 Earnings", date: "Apr 24", impact: "HIGH" },
                { symbol: "MSFT", headline: "Microsoft Q3 Earnings", date: "Apr 29", impact: "HIGH" },
              ].map((ex) => (
                <div key={ex.symbol} className="flex items-center gap-3 rounded-xl border border-border/40 bg-muted/5 px-3.5 py-2.5">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${IMPACT_DOT[ex.impact as keyof typeof IMPACT_DOT] ?? IMPACT_DOT.LOW}`} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">{ex.headline}</p>
                    <div className="mt-0.5 text-[10px] text-muted-foreground">{ex.date}</div>
                    <span className="font-mono text-[10px] text-muted-foreground">{ex.symbol}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          events.map((evt) => (
            <div
              key={evt.id}
              className="flex items-center gap-3 rounded-xl border border-border/40 bg-muted/5 px-3.5 py-2.5"
            >
              <span className={`h-2 w-2 shrink-0 rounded-full ${IMPACT_DOT[evt.impact] ?? IMPACT_DOT.LOW}`} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {evt.headline}
                </p>
                <div className="mt-0.5 text-[10px] text-muted-foreground">
                  {String(evt.raw_data?.date ?? "Date unavailable")}
                </div>
                {evt.symbols.length > 0 && (
                  <div className="mt-0.5 flex gap-1">
                    {evt.symbols.slice(0, 3).map((s) => (
                      <span key={s} className="font-mono text-[10px] text-muted-foreground">
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <span className="shrink-0 text-[10px] text-muted-foreground">
                {evt.source}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
