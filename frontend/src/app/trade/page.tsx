"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  RefreshCw,
  Unplug,
  TrendingUp,
} from "lucide-react";
import { OrderForm } from "@/components/trading/OrderForm";
import { PositionCard } from "@/components/trading/PositionCard";
import { TradeHistory } from "@/components/trading/TradeHistory";
import { TradingChart } from "@/components/charts/TradingChart";
import type { Account, Position } from "@/types/trading";
import type { TradeMarker } from "@/types/chart";
import { apiFetch } from "@/lib/api/client";
import { useTradingMode } from "@/hooks/useTradingMode";

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
  const { mode } = useTradingMode();

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const q = `?mode=${mode}`;
      const [accRes, posRes, tradeRes] = await Promise.allSettled([
        apiFetch<Account>(`/api/trading/account${q}`),
        apiFetch<{ positions: Position[] }>(`/api/trading/positions${q}`),
        apiFetch<any>(`/api/trading/trade-log?limit=100&mode=${mode}`),
      ]);

      let hasData = false;

      if (accRes.status === "fulfilled") {
        setAccount(accRes.value);
        hasData = true;
      }

      if (posRes.status === "fulfilled") {
        const data = posRes.value;
        setPositions(data.positions || []);
        hasData = true;
      }

      if (tradeRes.status === "fulfilled") {
        const data = tradeRes.value;
        setTrades(data.trades || data || []);
        hasData = true;
      }

      if (!hasData) setError(true);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  if (loading) {
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
            Connect a broker to start trading. Account data, positions, and trade history will appear here.
          </p>
        </div>
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
          onClick={fetchAll}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Account Summary Bar */}
      {account && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border border-border/50 bg-card p-4">
            <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">Cash Balance</div>
            <div className="text-base font-mono font-bold tabular-nums tracking-tight">{formatCurrency(account.cash)}</div>
          </div>
          <div className="rounded-xl border border-border/50 bg-card p-4">
            <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">Portfolio Value</div>
            <div className="text-base font-mono font-bold tabular-nums tracking-tight">{formatCurrency(account.portfolio_value)}</div>
          </div>
          <div className="rounded-xl border border-border/50 bg-card p-4">
            <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">Total Equity</div>
            <div className="text-base font-mono font-bold tabular-nums tracking-tight">{formatCurrency(account.equity)}</div>
          </div>
          <div className="rounded-xl border border-border/50 bg-card p-4">
            <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">Unrealized P&L</div>
            <div className={`text-base font-mono font-bold tabular-nums tracking-tight ${dayPnlUp ? "text-emerald-400" : "text-red-400"}`}>
              {dayPnlUp ? "+" : ""}${dayPnl.toFixed(2)}
            </div>
          </div>
        </div>
      )}

      {/* Main Content: Order Form + History | Positions */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left: Chart + Order Form + Trade History */}
        <div className="lg:col-span-3 space-y-5">
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
          <OrderForm onOrderPlaced={fetchAll} isPaperMode={mode === "paper"} />
          <TradeHistory trades={trades} />
        </div>

        {/* Right: Positions */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
              Open Positions
            </div>
            <span className="text-xs font-mono text-muted-foreground">{positions.length}</span>
          </div>
          {positions.length === 0 ? (
            <div className="rounded-xl border border-border/50 bg-card py-12 flex flex-col items-center gap-3 text-center px-4">
              <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-muted/50 border border-border/50">
                <TrendingUp className="h-4 w-4 text-muted-foreground/50" />
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">No open positions</div>
                <div className="text-xs text-muted-foreground/60 mt-0.5">Place an order to open a position</div>
              </div>
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
