"use client";

import { BarChart3 } from "lucide-react";
import { getMarketEvents, type MarketEvent } from "@/lib/reasoning-api";
import { usePolling } from "@/hooks/usePolling";

interface SectorData {
  symbol: string;
  move: number;
}

function parseSectorEvents(events: MarketEvent[]): SectorData[] {
  const sectors: SectorData[] = [];
  for (const evt of events) {
    if (evt.event_type !== "sector_move") continue;
    const symbol = String(evt.raw_data?.symbol ?? evt.symbols?.[0] ?? "").toUpperCase();
    const move = Number(evt.raw_data?.change_pct);
    if (!symbol || Number.isNaN(move)) continue;
    sectors.push({ symbol, move });
  }
  // Sort by absolute move descending
  return sectors.sort((a, b) => Math.abs(b.move) - Math.abs(a.move));
}

export function SectorMomentum() {
  const { data, loading, error } = usePolling<MarketEvent[]>({
    fetcher: () => getMarketEvents({ event_type: "sector_move", limit: 50 }),
    interval: 30_000,
  });
  const sectors = parseSectorEvents(data ?? []);

  const maxMove = Math.max(...sectors.map((s) => Math.abs(s.move)), 1);

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <BarChart3 className="h-3.5 w-3.5 text-violet-400" />
        Sector Momentum
      </div>

      <div className="mt-4 space-y-2">
        {loading ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-8 text-center text-sm text-muted-foreground">
            Loading sector momentum…
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-rose-400/20 bg-rose-400/5 px-4 py-8 text-center text-sm text-rose-300">
            Sector momentum unavailable. {error}
          </div>
        ) : sectors.length === 0 ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-8 text-center text-sm text-muted-foreground">
            No significant sector moves
          </div>
        ) : (
          sectors.map((s) => {
            const isPositive = s.move >= 0;
            const barWidth = (Math.abs(s.move) / maxMove) * 100;
            return (
              <div key={s.symbol} className="flex items-center gap-3">
                <span className="w-12 shrink-0 text-right font-mono text-xs font-medium text-muted-foreground">
                  {s.symbol}
                </span>
                <div className="flex-1">
                  <div className="h-5 w-full overflow-hidden rounded-md bg-muted/20">
                    <div
                      className={`h-full rounded-md transition-all duration-500 ${
                        isPositive ? "bg-emerald-400/60" : "bg-rose-400/60"
                      }`}
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                </div>
                <span
                  className={`w-16 shrink-0 text-right font-mono text-xs font-semibold ${
                    isPositive ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {isPositive ? "+" : ""}
                  {s.move.toFixed(2)}%
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
