"use client";

import React from "react";
import {
  DollarSign,
  Briefcase,
  TrendingUp,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";

function formatCurrency(val: number | null | undefined, decimals = 0): string {
  if (val == null) return "\u2014";
  return val.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function SkeletonCard({ label, icon: Icon }: { label: string; icon: React.ElementType }) {
  return (
    <div className="app-panel p-4">
      <div className="flex items-center gap-1.5 mb-2">
        <Icon className="h-3.5 w-3.5 text-muted-foreground/50" />
        <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          {label}
        </div>
      </div>
      <div className="h-6 w-24 animate-pulse bg-muted rounded" />
      <div className="h-3 w-16 animate-pulse bg-muted rounded mt-1.5" />
    </div>
  );
}

export function MetricsBar() {
  const account = useTradeStore((s) => s.account);
  const positions = useTradeStore((s) => s.positions);

  if (!account) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SkeletonCard label="Cash Balance" icon={DollarSign} />
        <SkeletonCard label="Portfolio Value" icon={Briefcase} />
        <SkeletonCard label="Total Equity" icon={BarChart3} />
        <SkeletonCard label="Unrealized P&L" icon={TrendingUp} />
      </div>
    );
  }

  const unrealizedPnl = positions.reduce(
    (sum, p) => sum + (p.unrealized_pnl ?? 0),
    0
  );
  const pnlUp = unrealizedPnl >= 0;

  const totalMarketValue = positions.reduce(
    (sum, p) => sum + (p.market_value ?? 0),
    0
  );

  // Calculate buying power usage
  const buyingPowerUsed =
    account.buying_power > 0
      ? ((account.equity - account.cash) / account.buying_power) * 100
      : 0;

  const cards = [
    {
      label: "Cash Balance",
      icon: DollarSign,
      value: formatCurrency(account.cash),
      sub: account.buying_power
        ? `${formatCurrency(account.buying_power, 0)} buying power`
        : null,
      subColor: "text-muted-foreground",
    },
    {
      label: "Portfolio Value",
      icon: Briefcase,
      value: formatCurrency(account.portfolio_value),
      sub: positions.length > 0
        ? `${positions.length} position${positions.length !== 1 ? "s" : ""}`
        : "No positions",
      subColor: "text-muted-foreground",
    },
    {
      label: "Total Equity",
      icon: BarChart3,
      value: formatCurrency(account.equity),
      sub:
        buyingPowerUsed > 0
          ? `${buyingPowerUsed.toFixed(1)}% utilized`
          : null,
      subColor:
        buyingPowerUsed > 80
          ? "text-red-400"
          : buyingPowerUsed > 50
            ? "text-amber-400"
            : "text-muted-foreground",
    },
    {
      label: "Unrealized P&L",
      icon: TrendingUp,
      value: `${pnlUp ? "+" : ""}${unrealizedPnl.toLocaleString("en-US", {
        style: "currency",
        currency: "USD",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })}`,
      valueColor: pnlUp ? "text-emerald-400" : "text-red-400",
      sub:
        totalMarketValue > 0 && unrealizedPnl !== 0
          ? `${pnlUp ? "+" : ""}${((unrealizedPnl / (totalMarketValue - unrealizedPnl)) * 100).toFixed(2)}%`
          : null,
      subColor: pnlUp ? "text-emerald-400/70" : "text-red-400/70",
      arrow: unrealizedPnl !== 0 ? (pnlUp ? ArrowUpRight : ArrowDownRight) : null,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {cards.map((card) => {
        const ArrowIcon = card.arrow;
        return (
          <div
            key={card.label}
            className="app-panel p-4 transition-colors hover:border-border"
          >
            <div className="flex items-center gap-1.5 mb-2">
              <card.icon className="h-3.5 w-3.5 text-muted-foreground/50" />
              <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
                {card.label}
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              <div
                className={`text-base font-mono font-bold tabular-nums tracking-tight ${
                  card.valueColor || ""
                }`}
              >
                {card.value}
              </div>
              {ArrowIcon && (
                <ArrowIcon
                  className={`h-4 w-4 ${card.valueColor || ""}`}
                />
              )}
            </div>
            {card.sub && (
              <div
                className={`text-[11px] font-medium mt-1 ${card.subColor}`}
              >
                {card.sub}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
