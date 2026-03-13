"use client";

import { useEffect, useState } from "react";
import { Calendar } from "lucide-react";
import { getMarketEvents, type MarketEvent } from "@/lib/reasoning-api";

const IMPACT_DOT = {
  HIGH: "bg-rose-400",
  MEDIUM: "bg-amber-400",
  LOW: "bg-slate-400",
};

export function EarningsCalendar() {
  const [events, setEvents] = useState<MarketEvent[]>([]);

  useEffect(() => {
    const fetch = () =>
      getMarketEvents({ event_type: "EARNINGS", limit: 20 }).then(setEvents).catch(() => {});
    fetch();
    const interval = setInterval(fetch, 60_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <Calendar className="h-3.5 w-3.5 text-amber-400" />
        Upcoming Earnings
      </div>

      <div className="mt-4 max-h-[320px] space-y-2 overflow-y-auto">
        {events.length === 0 ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-8 text-center text-sm text-muted-foreground">
            No upcoming earnings events
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
