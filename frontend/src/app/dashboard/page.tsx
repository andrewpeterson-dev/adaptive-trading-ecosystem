"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  Loader2,
  Unplug,
} from "lucide-react";
import type { Account, Position, Order, RiskSummary } from "@/types/trading";
import { apiFetch } from "@/lib/api/client";
import { SentimentPanel } from "@/components/analytics/SentimentPanel";
import { PortfolioRiskPanel } from "@/components/analytics/PortfolioRiskPanel";

function formatCurrency(val: number): string {
  return val.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    filled: "text-emerald-400 bg-emerald-400/10",
    pending: "text-amber-400 bg-amber-400/10",
    cancelled: "text-muted-foreground bg-muted",
    rejected: "text-red-400 bg-red-400/10",
    new: "text-blue-400 bg-blue-400/10",
    partially_filled: "text-amber-400 bg-amber-400/10",
  };
  const c = colors[status.toLowerCase()] || "text-muted-foreground bg-muted";
  return (
    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${c}`}>
      {status}
    </span>
  );
}

function GaugeBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="h-2 rounded-full bg-muted overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
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

  const fetchAll = useCallback(async () => {
    try {
      const [accRes, posRes, ordRes, riskRes] = await Promise.allSettled([
        apiFetch<Account>("/api/trading/account"),
        apiFetch<{ positions: Position[] }>("/api/trading/positions"),
        apiFetch<{ orders: Order[] }>("/api/trading/orders"),
        apiFetch<RiskSummary>("/api/trading/risk-summary"),
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
          Connect a broker (Alpaca or Webull) to view your trading dashboard with live account data, positions, and orders.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Trading Dashboard</h2>
          {lastRefresh && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Last updated {lastRefresh.toLocaleTimeString()}
            </p>
          )}
        </div>
        <button
          onClick={fetchAll}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Account + Risk cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Account Summary */}
        {account && (
          <div className="rounded-lg border border-border/50 bg-card p-5 space-y-4">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
              Account Summary
            </div>
            <div className="grid grid-cols-2 gap-4 tabular-nums">
              <div>
                <div className="text-xs text-muted-foreground">Equity</div>
                <div className="text-xl font-mono font-bold">{formatCurrency(account.equity)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Cash</div>
                <div className="text-xl font-mono font-bold">{formatCurrency(account.cash)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Buying Power</div>
                <div className="text-lg font-mono">{formatCurrency(account.buying_power)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Portfolio Value</div>
                <div className="text-lg font-mono">{formatCurrency(account.portfolio_value)}</div>
              </div>
            </div>
          </div>
        )}

        {/* Risk Status */}
        {risk && (
          <div className="rounded-lg border border-border/50 bg-card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
                Risk Status
              </div>
              {risk.is_halted && (
                <span className="text-xs font-bold px-2 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30">
                  HALTED
                </span>
              )}
            </div>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Drawdown</span>
                  <span className="font-mono">
                    {(risk.current_drawdown_pct * 100).toFixed(1)}% / {(risk.max_drawdown_limit_pct * 100).toFixed(0)}%
                  </span>
                </div>
                <GaugeBar
                  value={risk.current_drawdown_pct}
                  max={risk.max_drawdown_limit_pct}
                  color={risk.current_drawdown_pct / risk.max_drawdown_limit_pct > 0.7 ? "bg-red-500" : "bg-emerald-500"}
                />
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Exposure</span>
                  <span className="font-mono">
                    {(risk.current_exposure_pct * 100).toFixed(1)}% / {(risk.max_exposure_limit_pct * 100).toFixed(0)}%
                  </span>
                </div>
                <GaugeBar
                  value={risk.current_exposure_pct}
                  max={risk.max_exposure_limit_pct}
                  color={risk.current_exposure_pct / risk.max_exposure_limit_pct > 0.7 ? "bg-amber-500" : "bg-blue-500"}
                />
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Trades this hour</span>
                <span className="font-mono">{risk.trades_this_hour} / {risk.max_trades_per_hour}</span>
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
      <div className="rounded-lg border border-border/50 bg-card overflow-x-auto">
        <div className="px-4 py-3 border-b">
          <h3 className="text-sm font-semibold">
            Open Positions
            <span className="text-muted-foreground font-normal ml-2">{positions.length}</span>
          </h3>
        </div>
        {positions.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground text-sm">No open positions</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
                <th className="py-2 px-4">Symbol</th>
                <th className="py-2 px-4">Qty</th>
                <th className="py-2 px-4">Avg Entry</th>
                <th className="py-2 px-4">Current</th>
                <th className="py-2 px-4">Unrealized P&L</th>
                <th className="py-2 px-4">% Change</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const isUp = (p.unrealized_pnl ?? 0) >= 0;
                return (
                  <tr key={p.symbol} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                    <td className="py-2 px-4 font-medium font-mono">{p.symbol}</td>
                    <td className="py-2 px-4 font-mono">{p.quantity}</td>
                    <td className="py-2 px-4 font-mono">${p.avg_entry_price?.toFixed(2)}</td>
                    <td className="py-2 px-4 font-mono">${p.current_price?.toFixed(2)}</td>
                    <td className={`py-2 px-4 font-mono font-medium ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                      {isUp ? "+" : ""}${(p.unrealized_pnl ?? 0).toFixed(2)}
                    </td>
                    <td className={`py-2 px-4 font-mono text-xs ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                      {isUp ? "+" : ""}{((p.unrealized_pnl_pct ?? 0) * 100).toFixed(1)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Recent Orders Table */}
      <div className="rounded-lg border border-border/50 bg-card overflow-x-auto">
        <div className="px-4 py-3 border-b">
          <h3 className="text-sm font-semibold">
            Recent Orders
            <span className="text-muted-foreground font-normal ml-2">{orders.length}</span>
          </h3>
        </div>
        {orders.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground text-sm">No recent orders</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
                <th className="py-2 px-4">Symbol</th>
                <th className="py-2 px-4">Direction</th>
                <th className="py-2 px-4">Qty</th>
                <th className="py-2 px-4">Type</th>
                <th className="py-2 px-4">Status</th>
                <th className="py-2 px-4">Filled Price</th>
                <th className="py-2 px-4">Time</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                  <td className="py-2 px-4 font-medium font-mono">{o.symbol}</td>
                  <td className="py-2 px-4">
                    <span className={`text-xs font-medium ${o.direction === "long" ? "text-emerald-400" : "text-red-400"}`}>
                      {o.direction?.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-2 px-4 font-mono">{o.quantity}</td>
                  <td className="py-2 px-4 text-xs text-muted-foreground">{o.order_type}</td>
                  <td className="py-2 px-4"><StatusBadge status={o.status} /></td>
                  <td className="py-2 px-4 font-mono">{o.filled_price ? `$${o.filled_price.toFixed(2)}` : "—"}</td>
                  <td className="py-2 px-4 text-xs text-muted-foreground">{o.submitted_at?.slice(0, 16)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
