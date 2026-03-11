"use client";

import { useMemo } from "react";
import { Bot, BookOpen, Waves, Waypoints } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatCompactNumber, formatCurrency, formatLargeCurrency } from "@/lib/trading/format";
import { useTradeStore } from "@/stores/trade-store";
import { OptionsChainTab } from "./OptionsChainTab";
import { SymbolNewsFeed } from "./SymbolNewsFeed";

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[18px] border border-border/70 bg-muted/18 px-3 py-3">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

export function TradingInfoTabs() {
  const symbol = useTradeStore((state) => state.symbol);
  const snapshot = useTradeStore((state) => state.snapshot);
  const trades = useTradeStore((state) => state.trades);
  const positions = useTradeStore((state) => state.positions);
  const status = useTradeStore((state) => state.status);

  const symbolNotes = useMemo(
    () =>
      trades.filter(
        (trade) =>
          trade.symbol.toUpperCase() === symbol.toUpperCase() &&
          (trade.bot_explanation || trade.bot_name),
      ),
    [symbol, trades],
  );

  const activePosition = positions.find(
    (position) => position.symbol.toUpperCase() === symbol.toUpperCase(),
  );

  return (
    <div className="app-panel p-4 sm:p-5">
      <div className="mb-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Info Drawer
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          Snapshot, headlines, fundamentals, options, market depth, and AI trade notes for {symbol}.
        </p>
      </div>

      <Tabs defaultValue="overview">
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="news">News</TabsTrigger>
          <TabsTrigger value="fundamentals">Fundamentals</TabsTrigger>
          <TabsTrigger value="options">Options</TabsTrigger>
          <TabsTrigger value="depth">Depth/T&S</TabsTrigger>
          <TabsTrigger value="notes">AI Notes</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid gap-3 md:grid-cols-2">
            <DetailMetric label="Price" value={formatCurrency(snapshot?.price ?? snapshot?.last ?? null)} />
            <DetailMetric
              label="52 Week Range"
              value={
                snapshot?.fifty_two_week_low != null && snapshot?.fifty_two_week_high != null
                  ? `${formatCurrency(snapshot.fifty_two_week_low)} - ${formatCurrency(snapshot.fifty_two_week_high)}`
                  : "—"
              }
            />
            <DetailMetric label="Volume" value={formatCompactNumber(snapshot?.volume ?? null)} />
            <DetailMetric label="Average Volume" value={formatCompactNumber(snapshot?.avg_volume ?? null)} />
          </div>

          {snapshot?.name && (
            <div className="mt-4 rounded-[20px] border border-border/70 bg-muted/18 px-4 py-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <BookOpen className="h-4 w-4 text-primary" />
                {snapshot.name}
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {snapshot.exchange || "Exchange unavailable"} · Market status {snapshot.market_state || "unknown"}.
                {activePosition
                  ? ` You currently hold ${Math.abs(activePosition.quantity)} units in this symbol.`
                  : " No active position is currently open in this name."}
              </p>
            </div>
          )}

          <div className="mt-4">
            <SymbolNewsFeed symbol={symbol} limit={3} compact />
          </div>
        </TabsContent>

        <TabsContent value="news">
          <SymbolNewsFeed symbol={symbol} />
        </TabsContent>

        <TabsContent value="fundamentals">
          <div className="grid gap-3 md:grid-cols-2">
            <DetailMetric label="Market Cap" value={formatLargeCurrency(snapshot?.market_cap ?? null)} />
            <DetailMetric
              label="P / E"
              value={snapshot?.pe_ratio != null ? snapshot.pe_ratio.toFixed(2) : "—"}
            />
            <DetailMetric
              label="Dividend Yield"
              value={snapshot?.dividend_yield != null ? `${snapshot.dividend_yield.toFixed(2)}%` : "—"}
            />
            <DetailMetric label="Currency" value={snapshot?.currency || "USD"} />
            <DetailMetric label="Exchange" value={snapshot?.exchange || "—"} />
            <DetailMetric label="Feed Status" value={status?.market_data.status || "disconnected"} />
          </div>
        </TabsContent>

        <TabsContent value="options">
          <OptionsChainTab symbol={symbol} />
        </TabsContent>

        <TabsContent value="depth">
          <EmptyState
            icon={<Waves className="h-5 w-5 text-muted-foreground" />}
            title="Depth and Time & Sales not connected"
            description={`The trade tab is ready for Level II and tape data, but the current feed only exposes top-of-book quotes. Market data status: ${status?.market_data.status || "disconnected"}.`}
            className="border border-dashed border-border/70 bg-muted/15"
          />
        </TabsContent>

        <TabsContent value="notes">
          {symbolNotes.length === 0 ? (
            <EmptyState
              icon={<Bot className="h-5 w-5 text-muted-foreground" />}
              title="No AI notes for this symbol"
              description="Cerberus trade explanations and bot execution notes will appear here when bot activity touches the selected symbol."
              className="border border-dashed border-border/70 bg-muted/15"
            />
          ) : (
            <div className="space-y-3">
              {symbolNotes.map((trade) => (
                <div
                  key={trade.id}
                  className="rounded-[18px] border border-border/70 bg-background/70 px-4 py-4"
                >
                  <div className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    <Waypoints className="h-3.5 w-3.5" />
                    {trade.bot_name || "Bot Execution"}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-foreground">
                    {trade.bot_explanation || "No explanation returned."}
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
