"use client";

import { useMemo } from "react";
import { Activity, BookText, Bot, Newspaper, Sigma, Wallet } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useTradeStore } from "@/stores/trade-store";
import { OptionsPanel } from "@/components/trading/OptionsPanel";
import { SymbolNewsFeed } from "@/components/trading/SymbolNewsFeed";

function formatCurrency(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatLargeNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (value >= 1_000_000_000_000) return `${(value / 1_000_000_000_000).toFixed(2)}T`;
  if (value >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return value.toLocaleString();
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const normalized = value > 1 ? value / 100 : value;
  return `${(normalized * 100).toFixed(2)}%`;
}

export function TradingInfoDrawer() {
  const symbol = useTradeStore((state) => state.symbol);
  const snapshot = useTradeStore((state) => state.snapshot);
  const news = useTradeStore((state) => state.news);
  const newsLoading = useTradeStore((state) => state.newsLoading);
  const status = useTradeStore((state) => state.status);
  const trades = useTradeStore((state) => state.trades);

  const aiNotes = useMemo(
    () =>
      trades
        .filter(
          (trade) =>
            trade.symbol.toUpperCase() === symbol.toUpperCase() &&
            trade.bot_explanation &&
            trade.bot_explanation.trim().length > 0,
        )
        .slice(0, 6),
    [symbol, trades],
  );

  const metrics = [
    { label: "Last", value: formatCurrency(snapshot?.price ?? snapshot?.last) },
    { label: "Bid", value: formatCurrency(snapshot?.bid) },
    { label: "Ask", value: formatCurrency(snapshot?.ask) },
    { label: "Volume", value: formatLargeNumber(snapshot?.volume) },
    { label: "Market Cap", value: formatLargeNumber(snapshot?.market_cap) },
    { label: "P/E", value: snapshot?.pe_ratio != null ? snapshot.pe_ratio.toFixed(2) : "—" },
    {
      label: "52W Range",
      value:
        snapshot?.fifty_two_week_low != null && snapshot?.fifty_two_week_high != null
          ? `${formatCurrency(snapshot.fifty_two_week_low)} - ${formatCurrency(snapshot.fifty_two_week_high)}`
          : "—",
    },
    { label: "Dividend Yield", value: formatPercent(snapshot?.dividend_yield) },
  ];

  return (
    <div className="app-panel p-4 sm:p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Info Drawer
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Context for {symbol}, including news, fundamentals, options, and AI execution notes.
          </p>
        </div>
        {status?.broker && (
          <Badge variant="neutral" className="tracking-normal">
            <Wallet className="h-3.5 w-3.5" />
            {status.broker}
          </Badge>
        )}
      </div>

      <Tabs defaultValue="overview">
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="news">News</TabsTrigger>
          <TabsTrigger value="fundamentals">Fundamentals</TabsTrigger>
          <TabsTrigger value="options">Options</TabsTrigger>
          <TabsTrigger value="depth">Depth/T&amp;S</TabsTrigger>
          <TabsTrigger value="notes">AI Notes</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {metrics.slice(0, 4).map((metric) => (
              <div key={metric.label} className="rounded-2xl border border-border/60 bg-muted/20 p-3">
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  {metric.label}
                </div>
                <div className="mt-2 text-sm font-medium text-foreground">{metric.value}</div>
              </div>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Activity className="h-4 w-4 text-primary" />
                Market data status
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {status?.market_data.message || "Checking market data status."}
              </p>
            </div>
            <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <Sigma className="h-4 w-4 text-primary" />
                Routing status
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {status?.order_routing.message || "Checking routing status."}
              </p>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="news">
          <SymbolNewsFeed symbol={symbol} />
        </TabsContent>

        <TabsContent value="fundamentals">
          <div className="grid gap-3 sm:grid-cols-2">
            {metrics.map((metric) => (
              <div key={metric.label} className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  {metric.label}
                </div>
                <div className="mt-2 text-sm font-medium text-foreground">{metric.value}</div>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="options">
          <OptionsPanel />
        </TabsContent>

        <TabsContent value="depth">
          <EmptyState
            icon={<BookText className="h-5 w-5 text-muted-foreground" />}
            title="Depth and time-and-sales unavailable"
            description="Level II depth and tick-by-tick prints require a connected streaming data provider. The chart and quote ladder remain available while that feed is offline."
            className="min-h-[260px]"
          />
        </TabsContent>

        <TabsContent value="notes">
          {aiNotes.length === 0 ? (
            <EmptyState
              icon={<Bot className="h-5 w-5 text-muted-foreground" />}
              title="No AI execution notes"
              description={`Cerberus trade rationale for ${symbol} will appear here after bot-originated fills include explanation text.`}
              className="min-h-[260px]"
            />
          ) : (
            <div className="space-y-3">
              {aiNotes.map((note) => (
                <div key={note.id} className="rounded-2xl border border-border/60 bg-muted/20 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="info" className="tracking-normal">
                      <Newspaper className="h-3.5 w-3.5" />
                      {note.bot_name || "Cerberus bot"}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {note.filled_at || note.submitted_at}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-foreground">
                    {note.bot_explanation}
                  </p>
                </div>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
