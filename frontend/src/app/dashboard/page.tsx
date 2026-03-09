"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  RefreshCw,
  Loader2,
  Unplug,
  Settings,
  TrendingUp,
} from "lucide-react";
import type { Account, Position, Order, RiskSummary } from "@/types/trading";
import { apiFetch } from "@/lib/api/client";
import { useTradingMode } from "@/hooks/useTradingMode";
import { SentimentPanel } from "@/components/analytics/SentimentPanel";
import { PortfolioRiskPanel } from "@/components/analytics/PortfolioRiskPanel";

function formatCurrency(val: number): string {
  return val.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    filled: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
    pending: "text-amber-400 bg-amber-400/10 border-amber-400/20",
    cancelled: "text-muted-foreground bg-muted border-border/50",
    rejected: "text-red-400 bg-red-400/10 border-red-400/20",
    new: "text-blue-400 bg-blue-400/10 border-blue-400/20",
    partially_filled: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  };
  const c = colors[status.toLowerCase()] || "text-muted-foreground bg-muted border-border/50";
  return (
    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border uppercase tracking-wider ${c}`}>
      {status.replace("_", " ")}
    </span>
  );
}

function GaugeBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="h-1.5 rounded-full bg-muted overflow-hidden">
      <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SectionHeader({ children, count }: { children: React.ReactNode; count?: number }) {
  return (
    <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{children}</h3>
      {count !== undefined && (
        <span className="text-xs font-mono text-muted-foreground">{count}</span>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [account, setAccount] = useState<Account | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const { mode } = useTradingMode();

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const q = `?mode=${mode}`;
      const [accRes, posRes, ordRes, riskRes] = await Promise.allSettled([
        apiFetch<Account>(`/api/trading/account${q}`),
        apiFetch<{ positions: Position[] }>(`/api/trading/positions${q}`),
        apiFetch<{ orders: Order[] }>(`/api/trading/orders${q}`),
        apiFetch<RiskSummary>(`/api/trading/risk-summary${q}`),
      ]);

      if (accRes.status === "fulfilled") {
        setAccount(accRes.value);
        setError(false);
      } else {
        setError(true);
      }

      if (posRes.status === "fulfilled") {
        const data = posRes.value;
        setPositions(data.positions || []);
      }

      if (ordRes.status === "fulfilled") {
        const data = ordRes.value;
        const list = data.orders || [];
        setOrders(list.slice(0, 20));
      }

      if (riskRes.status === "fulfilled") {
        setRisk(riskRes.value);
      }

      setLastRefresh(new Date());
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
          <h2 className="text-base font-semibold">Broker not responding</h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
            Could not load account data. Your API key may need to be re-entered.
          </p>
        </div>
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={fetchAll}
            className="inline-flex items-center gap-2 rounded-lg border border-border/60 bg-secondary px-4 py-2 text-sm font-medium hover:bg-secondary/80 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
          <Link
            href="/settings"
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Settings className="h-4 w-4" />
            Go to Settings
          </Link>
        </div>
      </div>
    );
  }

  const drawdownRatio = risk ? risk.current_drawdown_pct / risk.max_drawdown_limit_pct : 0;
  const exposureRatio = risk ? risk.current_exposure_pct / risk.max_exposure_limit_pct : 0;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-lg font-semibold tracking-tight">Trading Dashboard</h1>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest border ${
                mode === "live"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
                  : "bg-muted text-muted-foreground border-border/50"
              }`}
            >
              {mode === "live" ? "Live" : "Paper"}
            </span>
          </div>
          {lastRefresh && (
            <p className="text-xs text-muted-foreground mt-0.5 font-mono">
              Updated {lastRefresh.toLocaleTimeString()}
            </p>
          )}
        </div>
        <button
          onClick={fetchAll}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Account + Risk cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Account Summary */}
        {account && (
          <div className="rounded-xl border border-border/50 bg-card p-5 space-y-4">
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
              Account Summary
            </div>
            {/* Primary equity number */}
            <div className="border-b border-border/40 pb-4">
              <div className="text-xs text-muted-foreground mb-1">Total Equity</div>
              <div className="text-3xl font-mono font-bold tabular-nums tracking-tight">
                {formatCurrency(account.equity)}
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Cash</div>
                <div className="text-sm font-mono font-semibold tabular-nums">{formatCurrency(account.cash)}</div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Buying Power</div>
                <div className="text-sm font-mono font-semibold tabular-nums">{formatCurrency(account.buying_power)}</div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">Portfolio</div>
                <div className="text-sm font-mono font-semibold tabular-nums">{formatCurrency(account.portfolio_value)}</div>
              </div>
            </div>
          </div>
        )}

        {/* Risk Status */}
        {risk && (
          <div className="rounded-xl border border-border/50 bg-card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                Risk Status
              </div>
              {risk.is_halted && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest bg-red-500/10 text-red-400 border border-red-500/20">
                  Halted
                </span>
              )}
            </div>
            <div className="space-y-4">
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-muted-foreground">Drawdown</span>
                  <span className={`font-mono font-semibold ${drawdownRatio > 0.7 ? "text-red-400" : drawdownRatio > 0.4 ? "text-amber-400" : "text-emerald-400"}`}>
                    {(risk.current_drawdown_pct * 100).toFixed(1)}%
                    <span className="text-muted-foreground font-normal"> / {(risk.max_drawdown_limit_pct * 100).toFixed(0)}%</span>
                  </span>
                </div>
                <GaugeBar
                  value={risk.current_drawdown_pct}
                  max={risk.max_drawdown_limit_pct}
                  color={drawdownRatio > 0.7 ? "bg-red-500" : drawdownRatio > 0.4 ? "bg-amber-500" : "bg-emerald-500"}
                />
              </div>
              <div className="space-y-1.5">
                <div className="flex justify-between items-center text-xs">
                  <span className="text-muted-foreground">Exposure</span>
                  <span className={`font-mono font-semibold ${exposureRatio > 0.7 ? "text-amber-400" : "text-blue-400"}`}>
                    {(risk.current_exposure_pct * 100).toFixed(1)}%
                    <span className="text-muted-foreground font-normal"> / {(risk.max_exposure_limit_pct * 100).toFixed(0)}%</span>
                  </span>
                </div>
                <GaugeBar
                  value={risk.current_exposure_pct}
                  max={risk.max_exposure_limit_pct}
                  color={exposureRatio > 0.7 ? "bg-amber-500" : "bg-blue-500"}
                />
              </div>
              <div className="flex justify-between items-center text-xs pt-1 border-t border-border/40">
                <span className="text-muted-foreground">Trades this hour</span>
                <span className="font-mono font-semibold tabular-nums">
                  {risk.trades_this_hour}
                  <span className="text-muted-foreground font-normal"> / {risk.max_trades_per_hour}</span>
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Sentiment + Portfolio Risk */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SentimentPanel />
        <PortfolioRiskPanel />
      </div>

      {/* Positions Table */}
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        <SectionHeader count={positions.length}>Open Positions</SectionHeader>
        {positions.length === 0 ? (
          <div className="py-16 flex flex-col items-center gap-3 text-center">
            <div className="inline-flex items-center justify-center h-12 w-12 rounded-full bg-muted/50 border border-border/50">
              <TrendingUp className="h-5 w-5 text-muted-foreground/50" />
            </div>
            <div>
              <div className="text-sm font-medium text-muted-foreground">No open positions</div>
              <div className="text-xs text-muted-foreground/60 mt-0.5">Execute a trade to open a position</div>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border/50 bg-muted/20 text-[10px] text-muted-foreground uppercase tracking-widest">
                  <th className="py-2.5 px-4 font-semibold">Symbol</th>
                  <th className="py-2.5 px-4 font-semibold">Qty</th>
                  <th className="py-2.5 px-4 font-semibold">Avg Entry</th>
                  <th className="py-2.5 px-4 font-semibold">Current</th>
                  <th className="py-2.5 px-4 font-semibold">Unrealized P&L</th>
                  <th className="py-2.5 px-4 font-semibold">Change</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p, i) => {
                  const isUp = (p.unrealized_pnl ?? 0) >= 0;
                  return (
                    <tr
                      key={p.symbol}
                      className={`border-b border-border/40 hover:bg-muted/20 transition-colors ${
                        i % 2 === 1 ? "bg-muted/5" : ""
                      }`}
                    >
                      <td className="py-2.5 px-4 font-mono font-semibold text-sm tracking-wide">{p.symbol}</td>
                      <td className="py-2.5 px-4 font-mono text-sm tabular-nums">{p.quantity}</td>
                      <td className="py-2.5 px-4 font-mono text-sm tabular-nums">${p.avg_entry_price?.toFixed(2)}</td>
                      <td className="py-2.5 px-4 font-mono text-sm tabular-nums">${p.current_price?.toFixed(2)}</td>
                      <td className={`py-2.5 px-4 font-mono text-sm font-semibold tabular-nums ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                        {isUp ? "+" : ""}${(p.unrealized_pnl ?? 0).toFixed(2)}
                      </td>
                      <td className={`py-2.5 px-4 font-mono text-xs tabular-nums ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                        {isUp ? "+" : ""}{((p.unrealized_pnl_pct ?? 0) * 100).toFixed(2)}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent Orders Table */}
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        <SectionHeader count={orders.length}>Recent Orders</SectionHeader>
        {orders.length === 0 ? (
          <div className="py-10 text-center text-sm text-muted-foreground">
            No recent orders
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border/50 bg-muted/20 text-[10px] text-muted-foreground uppercase tracking-widest">
                  <th className="py-2.5 px-4 font-semibold">Symbol</th>
                  <th className="py-2.5 px-4 font-semibold">Side</th>
                  <th className="py-2.5 px-4 font-semibold">Qty</th>
                  <th className="py-2.5 px-4 font-semibold">Type</th>
                  <th className="py-2.5 px-4 font-semibold">Status</th>
                  <th className="py-2.5 px-4 font-semibold">Filled</th>
                  <th className="py-2.5 px-4 font-semibold">Time</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o, i) => (
                  <tr
                    key={o.id}
                    className={`border-b border-border/40 hover:bg-muted/20 transition-colors ${
                      i % 2 === 1 ? "bg-muted/5" : ""
                    }`}
                  >
                    <td className="py-2.5 px-4 font-mono font-semibold text-sm tracking-wide">{o.symbol}</td>
                    <td className="py-2.5 px-4">
                      <span className={`text-xs font-bold uppercase tracking-wider ${o.direction === "long" ? "text-emerald-400" : "text-red-400"}`}>
                        {o.direction}
                      </span>
                    </td>
                    <td className="py-2.5 px-4 font-mono text-sm tabular-nums">{o.quantity}</td>
                    <td className="py-2.5 px-4 text-xs text-muted-foreground uppercase tracking-wide">{o.order_type}</td>
                    <td className="py-2.5 px-4"><StatusBadge status={o.status} /></td>
                    <td className="py-2.5 px-4 font-mono text-sm tabular-nums">
                      {o.filled_price ? `$${o.filled_price.toFixed(2)}` : <span className="text-muted-foreground/50">—</span>}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-xs text-muted-foreground tabular-nums">{o.submitted_at?.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
