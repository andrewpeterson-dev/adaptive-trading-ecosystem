"use client";

import React, { useEffect, useCallback, useMemo } from "react";
import {
  Loader2,
  RefreshCw,
  Unplug,
} from "lucide-react";
import { StockOrderTicket } from "@/components/trading/StockOrderTicket";
import { OptionsPanel } from "@/components/trading/OptionsPanel";
import { PositionsPanel } from "@/components/trading/PositionsPanel";
import { TradeHistoryPanel } from "@/components/trading/TradeHistoryPanel";
import { TradingChart } from "@/components/charts/TradingChart";
import { MetricsBar } from "@/components/trading/MetricsBar";
import { SymbolSearch } from "@/components/trading/SymbolSearch";
import { AssetModeSwitch } from "@/components/trading/AssetModeSwitch";
import { PageHeader } from "@/components/layout/PageHeader";
import { useTradeStore } from "@/stores/trade-store";
import type { TradeMarker } from "@/types/chart";
import { useTradingMode } from "@/hooks/useTradingMode";

export default function TradePage() {
  const { mode } = useTradingMode();
  const {
    symbol,
    assetMode,
    account,
    trades,
    loading,
    error,
    highlightedTradeId,
    fetchAll,
  } = useTradeStore();

  const refresh = useCallback(() => {
    fetchAll(mode);
  }, [fetchAll, mode]);

  // Initial fetch + 30s polling
  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [refresh]);

  // Build trade markers for chart, filtering by current symbol
  const tradeMarkers: TradeMarker[] = useMemo(() => {
    return trades
      .filter((t) => {
        const tradeSymbol = (t.symbol || "").toUpperCase();
        const matchesSymbol = tradeSymbol === symbol.toUpperCase();
        const hasFill = t.filled_at && t.filled_price;
        return matchesSymbol && hasFill;
      })
      .map((t) => ({
        time: Math.floor(new Date(t.filled_at!).getTime() / 1000),
        price: t.filled_price!,
        side: (t.direction === "buy" || t.direction === "long") ? "buy" as const : "sell" as const,
        tradeId: t.id,
        label: t.bot_name || undefined,
      }));
  }, [trades, symbol]);

  if (loading && !account) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !account) {
    return (
      <div className="text-center py-32 space-y-4">
        <div className="inline-flex items-center justify-center h-14 w-14 rounded-full bg-muted/50 border border-border/50 mx-auto">
          <Unplug className="h-6 w-6 text-muted-foreground/60" />
        </div>
        <div>
          <h2 className="text-base font-semibold">No broker connected</h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
            Connect a broker to start trading. Account data, positions, and
            trade history will appear here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Execution"
        title={`${mode === "live" ? "Live" : "Paper"} Trading`}
        description="Monitor quotes, stage orders, and manage positions from one trading workspace without jumping between modules."
        badge={
          <span className="app-pill">
            <span
              className={`h-2 w-2 rounded-full ${
                mode === "live" ? "bg-emerald-400" : "bg-primary"
              }`}
            />
            {mode === "live" ? "Real Money" : "Simulated Capital"}
          </span>
        }
        actions={
          <button onClick={refresh} className="app-button-secondary">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        }
      />

      <MetricsBar />

      <div className="app-panel p-4 sm:p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center">
          <div className="flex-1">
            <SymbolSearch />
          </div>
          <AssetModeSwitch />
        </div>

        {assetMode === "options" && (
          <div className="mt-4">
            <span className="app-pill">
              Underlying chart
              <span className="font-mono tracking-normal text-foreground">
                {symbol}
              </span>
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-7 xl:col-span-8">
          <TradingChart
            symbol={symbol}
            trades={tradeMarkers}
            highlightedTradeId={highlightedTradeId}
          />
          <TradeHistoryPanel />
        </div>

        <div className="space-y-6 lg:col-span-5 xl:col-span-4">
          {assetMode === "options" ? (
            <OptionsPanel />
          ) : (
            <StockOrderTicket
              onOrderPlaced={refresh}
              isPaperMode={mode === "paper"}
            />
          )}

          <PositionsPanel onClose={refresh} />
        </div>
      </div>
    </div>
  );
}
