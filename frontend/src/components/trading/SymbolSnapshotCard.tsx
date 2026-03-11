"use client";

import { BookmarkPlus, BookOpenText, Building2, LineChart, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { SymbolSnapshot } from "@/types/trading";
import {
  formatCompactNumber,
  formatCurrency,
  formatPercent,
} from "@/lib/trading/format";

interface SymbolSnapshotCardProps {
  snapshot: SymbolSnapshot | null;
  loading?: boolean;
  isWatched: boolean;
  onToggleWatchlist: () => void;
  onOpenResearch: () => void;
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/25 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

export function SymbolSnapshotCard({
  snapshot,
  loading = false,
  isWatched,
  onToggleWatchlist,
  onOpenResearch,
}: SymbolSnapshotCardProps) {
  if (!snapshot && !loading) {
    return (
      <div className="app-panel p-4">
        <EmptyState
          icon={<LineChart className="h-5 w-5 text-muted-foreground" />}
          title="Select a symbol"
          description="Search for a ticker to load a live snapshot, key fundamentals, and related headlines."
          className="py-8"
        />
      </div>
    );
  }

  const change = snapshot?.change ?? null;
  const changePct = snapshot?.change_pct ?? null;
  const positive = change != null && change >= 0;
  const rangeLabel =
    snapshot?.fifty_two_week_low != null && snapshot?.fifty_two_week_high != null
      ? `${formatCurrency(snapshot.fifty_two_week_low)} - ${formatCurrency(snapshot.fifty_two_week_high)}`
      : "—";

  return (
    <div className="app-panel p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-lg font-semibold tracking-tight text-foreground">
              {snapshot?.symbol || "—"}
            </span>
            {snapshot?.exchange && (
              <span className="rounded-full border border-border/70 bg-muted/35 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                {snapshot.exchange}
              </span>
            )}
          </div>

          <div>
            <p className="text-sm font-medium text-foreground">
              {loading ? "Loading symbol snapshot..." : snapshot?.name || "Unknown instrument"}
            </p>
            {snapshot?.price != null && (
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <span className="text-2xl font-semibold tracking-tight text-foreground">
                  {formatCurrency(snapshot.price)}
                </span>
                {change != null && changePct != null && (
                  <span
                    className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                      positive
                        ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                        : "border-red-500/25 bg-red-500/10 text-red-200"
                    }`}
                  >
                    {positive ? "+" : ""}
                    {formatCurrency(change)} ({formatPercent(changePct)})
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Button onClick={onToggleWatchlist} variant={isWatched ? "secondary" : "primary"} size="sm">
            {isWatched ? <Star className="h-3.5 w-3.5" /> : <BookmarkPlus className="h-3.5 w-3.5" />}
            {isWatched ? "In Watchlist" : "Add to Watchlist"}
          </Button>
          <Button onClick={onOpenResearch} variant="secondary" size="sm">
            <BookOpenText className="h-3.5 w-3.5" />
            Open in Research
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Metric label="Volume" value={formatCompactNumber(snapshot?.volume)} />
        <Metric label="Market Cap" value={formatCompactNumber(snapshot?.market_cap)} />
        <Metric label="P/E" value={snapshot?.pe_ratio != null ? snapshot.pe_ratio.toFixed(2) : "—"} />
        <Metric label="52 Week Range" value={rangeLabel} />
        <Metric label="Dividend Yield" value={formatPercent(snapshot?.dividend_yield)} />
        <Metric label="Average Volume" value={formatCompactNumber(snapshot?.avg_volume)} />
      </div>

      {(snapshot?.sector || snapshot?.industry || snapshot?.description) && (
        <div className="mt-4 rounded-3xl border border-border/60 bg-muted/20 p-4">
          <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            <Building2 className="h-3.5 w-3.5" />
            <span>{snapshot.sector || "Market"}</span>
            {snapshot.industry && <span>/ {snapshot.industry}</span>}
          </div>
          {snapshot.description && (
            <p className="mt-2 line-clamp-4 text-sm leading-6 text-muted-foreground">
              {snapshot.description}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
