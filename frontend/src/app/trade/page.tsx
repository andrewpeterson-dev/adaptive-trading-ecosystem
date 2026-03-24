"use client";

import React, { useCallback, useEffect, useMemo } from "react";
import Link from "next/link";
import { Loader2, RefreshCw, Settings, Unplug } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TradingWorkspace } from "@/components/trading/TradingWorkspace";
import { useTradeStore } from "@/stores/trade-store";
import { useTradingMode } from "@/hooks/useTradingMode";
import type { TradeMarker } from "@/types/chart";

export default function TradePage() {
  const { mode } = useTradingMode();
  const {
    symbol,
    account,
    trades,
    loading,
    error,
    highlightedTradeId,
    fetchAll,
  } = useTradeStore();

  const refresh = useCallback(() => {
    void fetchAll(mode);
  }, [fetchAll, mode]);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, 30000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  const tradeMarkers: TradeMarker[] = useMemo(() => {
    return trades
      .filter((trade) => {
        const tradeSymbol = (trade.symbol || "").toUpperCase();
        return tradeSymbol === symbol.toUpperCase() && trade.filled_at && trade.filled_price;
      })
      .map((trade) => ({
        time: Math.floor(new Date(trade.filled_at!).getTime() / 1000),
        price: trade.filled_price!,
        side: trade.direction === "buy" || trade.direction === "long" ? "buy" : "sell",
        tradeId: trade.id,
        label: trade.bot_name || undefined,
      }));
  }, [symbol, trades]);

  if (loading && !account) {
    return (
      <div className="app-page space-y-4">
        <div className="h-10 w-64 animate-pulse rounded-lg bg-muted/20" />
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
          <div className="h-[420px] animate-pulse rounded-2xl bg-muted/20" />
          <div className="space-y-3">
            <div className="h-32 animate-pulse rounded-2xl bg-muted/20" />
            <div className="h-32 animate-pulse rounded-2xl bg-muted/20" />
            <div className="h-48 animate-pulse rounded-2xl bg-muted/20" />
          </div>
        </div>
      </div>
    );
  }

  if (error && !account) {
    return (
      <div className="app-page">
        <div className="app-panel">
          <EmptyState
            icon={<Unplug className="h-5 w-5 text-muted-foreground/70" />}
            title="No broker connected"
            description="Connect Alpaca or Webull to start trading. Account data, positions, and trade history will appear here."
            action={
              <Link
                href="/settings/api-connections"
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Settings className="h-4 w-4" />
                Connect Broker
              </Link>
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className="app-page">
      <SubNav items={[
        { href: "/trade", label: "Workspace" },
        { href: "/trade-analysis", label: "Deep Analysis" },
        { href: "/watchlist", label: "Watchlist" },
      ]} />

      <PageHeader
        eyebrow="Execution"
        title={`${mode === "live" ? "Live" : "Paper"} Trading`}
        description="Search symbols, keep context beside the chart, collapse drawers when you need focus, and manage the full order workflow from one workspace."
        badge={
          <span className="app-pill">
            <span
              className={`h-2 w-2 rounded-full ${mode === "live" ? "bg-emerald-400" : "bg-primary"}`}
            />
            {mode === "live" ? "Real Money" : "Simulated Capital"}
          </span>
        }
        actions={
          <Button onClick={refresh} variant="secondary" size="sm">
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />
      <TradingWorkspace
        tradeMarkers={tradeMarkers}
        highlightedTradeId={highlightedTradeId}
        onRefresh={refresh}
        isPaperMode={mode === "paper"}
      />
    </div>
  );
}
