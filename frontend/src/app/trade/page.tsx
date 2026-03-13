"use client";

import React, { useCallback, useEffect, useMemo } from "react";
import { Loader2, RefreshCw, Unplug } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { Button } from "@/components/ui/button";
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
      <div className="flex items-center justify-center py-32">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !account) {
    return (
      <div className="space-y-4 py-32 text-center">
        <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-full border border-border/50 bg-muted/50">
          <Unplug className="h-6 w-6 text-muted-foreground/60" />
        </div>
        <div>
          <h2 className="text-base font-semibold">No broker connected</h2>
          <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">
            Connect a broker to start trading. Account data, positions, and trade history will appear here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-page">
      <SubNav items={[
        { href: "/trade", label: "Workspace" },
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
