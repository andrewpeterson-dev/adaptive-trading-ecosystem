"use client";

import React, { useEffect, useCallback } from "react";
import {
  Loader2,
  RefreshCw,
  Unplug,
  TrendingUp,
} from "lucide-react";
import { StockOrderTicket } from "@/components/trading/StockOrderTicket";
import { PositionCard } from "@/components/trading/PositionCard";
import { TradeHistory } from "@/components/trading/TradeHistory";
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
    positions,
    trades,
    loading,
    error,
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

  const tradeMarkers: TradeMarker[] = trades
    .filter((t: any) => t.filled_at && t.filled_price)
    .map(
      (t: any): TradeMarker => ({
        time: Math.floor(new Date(t.filled_at).getTime() / 1000),
        price: t.filled_price,
        side: t.direction === "buy" ? "buy" : "sell",
      })
    );

  return (
    <div className="space-y-6">
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

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left Column: Symbol Search + Chart + Trade History */}
        <div className="lg:col-span-3 space-y-5">
          <SymbolSearch />
          <TradingChart symbol={symbol} trades={tradeMarkers} />
          <TradeHistory trades={trades} />
        </div>

        {/* Right Column: Asset Mode + Order Ticket + Positions */}
        <div className="lg:col-span-2 space-y-5">
          <AssetModeSwitch />

          {/* Order Ticket Area */}
          {assetMode === "options" ? (
            <div className="rounded-xl border border-border/50 bg-card p-6 flex flex-col items-center justify-center gap-2 text-center min-h-[200px]">
              <div className="text-sm font-medium text-muted-foreground">
                Options panel coming soon
              </div>
              <div className="text-xs text-muted-foreground/60">
                Options trading will be available in a future update
              </div>
            </div>
          ) : (
            <StockOrderTicket onOrderPlaced={refresh} isPaperMode={mode === "paper"} />
          )}

          {/* Positions */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                Open Positions
              </div>
              <span className="text-xs font-mono text-muted-foreground">
                {positions.length}
              </span>
            </div>
            {positions.length === 0 ? (
              <div className="rounded-xl border border-border/50 bg-card py-12 flex flex-col items-center gap-3 text-center px-4">
                <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-muted/50 border border-border/50">
                  <TrendingUp className="h-4 w-4 text-muted-foreground/50" />
                </div>
                <div>
                  <div className="text-sm font-medium text-muted-foreground">
                    No open positions
                  </div>
                  <div className="text-xs text-muted-foreground/60 mt-0.5">
                    Place an order to open a position
                  </div>
                </div>
              </div>
            ) : (
              positions.map((p) => (
                <PositionCard
                  key={p.symbol}
                  position={p}
                  onClose={refresh}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
