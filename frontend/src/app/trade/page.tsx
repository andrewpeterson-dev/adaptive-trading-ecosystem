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
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-lg font-semibold tracking-tight">
              {mode === "live" ? "Live" : "Paper"} Trading
            </h1>
            {mode === "live" && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                Real Money
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Execute trades and manage positions
          </p>
        </div>
        <button
          onClick={refresh}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Metrics Bar */}
      <MetricsBar />

      {/* Symbol Search + Asset Mode Switch row */}
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <SymbolSearch />
        </div>
        <AssetModeSwitch />
      </div>

      {/* Underlying indicator for options mode */}
      {assetMode === "options" && (
        <div className="text-xs text-muted-foreground -mt-2">
          Chart showing underlying: <span className="font-mono font-medium text-foreground">{symbol}</span>
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Chart + Trade History */}
        <div className="lg:col-span-7 xl:col-span-8 space-y-5">
          <TradingChart
            symbol={symbol}
            trades={tradeMarkers}
            highlightedTradeId={highlightedTradeId}
          />
          <TradeHistoryPanel />
        </div>

        {/* Right Column: Order Ticket + Positions */}
        <div className="lg:col-span-5 xl:col-span-4 space-y-5">
          {/* Order Ticket Area */}
          {assetMode === "options" ? (
            <OptionsPanel />
          ) : (
            <StockOrderTicket onOrderPlaced={refresh} isPaperMode={mode === "paper"} />
          )}

          {/* Positions */}
          <PositionsPanel onClose={refresh} />
        </div>
      </div>
    </div>
  );
}
