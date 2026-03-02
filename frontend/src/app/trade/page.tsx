"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  RefreshCw,
  Unplug,
} from "lucide-react";
import { OrderForm } from "@/components/trading/OrderForm";
import { PositionCard } from "@/components/trading/PositionCard";
import { TradeHistory } from "@/components/trading/TradeHistory";
import { TradingChart } from "@/components/charts/TradingChart";
import type { Account, Position } from "@/types/trading";
import type { TradeMarker } from "@/types/chart";

function formatCurrency(val: number): string {
  return val.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export default function TradePage() {
  const [account, setAccount] = useState<Account | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [accRes, posRes, tradeRes] = await Promise.allSettled([
        fetch("/api/trading/account"),
        fetch("/api/trading/positions"),
        fetch("/api/trading/trade-log?limit=100"),
      ]);

      let hasData = false;

      if (accRes.status === "fulfilled" && accRes.value.ok) {
        setAccount(await accRes.value.json());
        hasData = true;
      }

      if (posRes.status === "fulfilled" && posRes.value.ok) {
        const data = await posRes.value.json();
        setPositions(data.positions || data || []);
        hasData = true;
      }

      if (tradeRes.status === "fulfilled" && tradeRes.value.ok) {
        const data = await tradeRes.value.json();
        setTrades(data.trades || data || []);
        hasData = true;
      }

      if (!hasData) setError(true);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !account) {
    return (
      <div className="text-center py-20 space-y-3">
        <Unplug className="h-10 w-10 text-muted-foreground/40 mx-auto" />
        <h2 className="text-lg font-semibold">No Broker Connected</h2>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          Connect a broker to start paper trading. Account data, positions, and trade history will appear here.
        </p>
      </div>
    );
  }

  const dayPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);
  const dayPnlUp = dayPnl >= 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Paper Trading</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Execute trades and manage positions
          </p>
        </div>
        <button
          onClick={fetchAll}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Account Summary Bar */}
      {account && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="rounded-lg border border-border/50 bg-card p-4">
            <div className="text-xs text-muted-foreground mb-1">Cash Balance</div>
            <div className="text-lg font-mono font-bold tabular-nums">{formatCurrency(account.cash)}</div>
          </div>
          <div className="rounded-lg border border-border/50 bg-card p-4">
            <div className="text-xs text-muted-foreground mb-1">Portfolio Value</div>
            <div className="text-lg font-mono font-bold tabular-nums">{formatCurrency(account.portfolio_value)}</div>
          </div>
          <div className="rounded-lg border border-border/50 bg-card p-4">
            <div className="text-xs text-muted-foreground mb-1">Total Equity</div>
            <div className="text-lg font-mono font-bold tabular-nums">{formatCurrency(account.equity)}</div>
          </div>
          <div className="rounded-lg border border-border/50 bg-card p-4">
            <div className="text-xs text-muted-foreground mb-1">Day P&L</div>
            <div className={`text-lg font-mono font-bold tabular-nums ${dayPnlUp ? "text-emerald-400" : "text-red-400"}`}>
              {dayPnlUp ? "+" : ""}${dayPnl.toFixed(2)}
            </div>
          </div>
        </div>
      )}

      {/* Main Content: Order Form + History | Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left: Chart + Order Form + Trade History (60%) */}
        <div className="lg:col-span-3 space-y-6">
          <TradingChart
            symbol="SPY"
            trades={trades
              .filter((t: any) => t.filled_at && t.filled_price)
              .map((t: any): TradeMarker => ({
                time: Math.floor(new Date(t.filled_at).getTime() / 1000),
                price: t.filled_price,
                side: t.direction === "buy" ? "buy" : "sell",
              }))}
          />
          <OrderForm onOrderPlaced={fetchAll} />
          <TradeHistory trades={trades} />
        </div>

        {/* Right: Positions (40%) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
            Positions
            <span className="text-xs font-normal">({positions.length})</span>
          </div>
          {positions.length === 0 ? (
            <div className="rounded-lg border border-border/50 bg-card py-8 text-center text-muted-foreground text-sm">
              No open positions
            </div>
          ) : (
            positions.map((p) => (
              <PositionCard
                key={p.symbol}
                position={p}
                onClose={fetchAll}
              />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
