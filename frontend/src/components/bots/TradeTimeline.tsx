"use client";

import type { TimelineBucket, TimelineGranularity } from "@/lib/bot-visualization";
import { formatCompactCurrency } from "@/lib/bot-visualization";

interface TradeTimelineProps {
  buckets: TimelineBucket[];
  granularity: TimelineGranularity;
  onGranularityChange: (granularity: TimelineGranularity) => void;
  currentIndex: number;
  onIndexChange: (index: number) => void;
}

const GRANULARITIES: Array<{ value: TimelineGranularity; label: string }> = [
  { value: "day", label: "Day view" },
  { value: "week", label: "Week view" },
  { value: "month", label: "Month view" },
];

export function TradeTimeline({
  buckets,
  granularity,
  onGranularityChange,
  currentIndex,
  onIndexChange,
}: TradeTimelineProps) {
  const currentBucket = buckets[currentIndex] ?? null;
  const maxTrades = Math.max(...buckets.map((bucket) => bucket.tradeCount), 1);

  return (
    <section className="app-panel p-5 sm:p-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Timeline View
          </div>
          <h3 className="mt-1 text-lg font-semibold text-foreground">Scrub through bot activity</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Move across time buckets to replay when trades start appearing on the chart.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {GRANULARITIES.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => onGranularityChange(item.value)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold tracking-[0.12em] transition-colors ${
                granularity === item.value
                  ? "bg-foreground text-background"
                  : "bg-muted/15 text-muted-foreground hover:text-foreground"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {buckets.length === 0 ? (
        <div className="mt-5 rounded-[22px] border border-border/60 bg-muted/10 px-4 py-8 text-center text-sm text-muted-foreground">
          Trade replay becomes available once the bot has timestamped executions.
        </div>
      ) : (
        <>
          <div className="mt-5 rounded-[22px] border border-border/60 bg-muted/10 p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Active Window
                </div>
                <div className="mt-1 text-lg font-semibold text-foreground">{currentBucket?.label}</div>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Trades</div>
                  <div className="mt-1 text-sm font-semibold text-foreground">{currentBucket?.tradeCount ?? 0}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Wins</div>
                  <div className="mt-1 text-sm font-semibold text-foreground">{currentBucket?.winCount ?? 0}</div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">PnL</div>
                  <div className={`mt-1 text-sm font-semibold ${(currentBucket?.totalNetPnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {formatCompactCurrency(currentBucket?.totalNetPnl ?? 0)}
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-5 flex items-end gap-2 overflow-x-auto pb-2">
              {buckets.map((bucket, index) => {
                const height = 36 + (bucket.tradeCount / maxTrades) * 84;
                const active = index === currentIndex;
                return (
                  <button
                    key={bucket.key}
                    type="button"
                    onClick={() => onIndexChange(index)}
                    className="flex min-w-[54px] flex-col items-center gap-2"
                  >
                    <div
                      className={`w-full rounded-t-2xl border border-white/10 transition-all ${
                        active
                          ? bucket.totalNetPnl >= 0
                            ? "bg-emerald-400 shadow-[0_0_0_1px_rgba(16,185,129,0.18)]"
                            : "bg-rose-400 shadow-[0_0_0_1px_rgba(244,63,94,0.18)]"
                          : bucket.totalNetPnl >= 0
                            ? "bg-emerald-400/35"
                            : "bg-rose-400/35"
                      }`}
                      style={{ height }}
                    />
                    <span className={`text-[10px] ${active ? "text-foreground" : "text-muted-foreground"}`}>
                      {bucket.label}
                    </span>
                  </button>
                );
              })}
            </div>

            <input
              className="mt-4 w-full accent-sky-500"
              type="range"
              min={0}
              max={Math.max(buckets.length - 1, 0)}
              step={1}
              value={Math.min(currentIndex, Math.max(buckets.length - 1, 0))}
              onChange={(event) => onIndexChange(Number(event.target.value))}
            />
          </div>
        </>
      )}
    </section>
  );
}
