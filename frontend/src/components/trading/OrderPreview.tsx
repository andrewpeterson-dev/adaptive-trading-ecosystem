"use client";

import React from "react";
import { useTradeStore } from "@/stores/trade-store";

interface OrderPreviewProps {
  quantity: number;
  price: number | null;
  direction: "buy" | "sell";
  symbol?: string;
}

function fmt(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function OrderPreview({
  quantity,
  price,
  direction,
  symbol,
}: OrderPreviewProps) {
  const { account, positions } = useTradeStore();

  if (quantity <= 0 || price == null || price <= 0 || !account) return null;

  const cost = quantity * price;
  const isBuy = direction === "buy";
  const remainingCash = isBuy ? account.cash - cost : account.cash + cost;
  const portfolioPct =
    account.portfolio_value > 0 ? (cost / account.portfolio_value) * 100 : null;

  const existingPosition = symbol
    ? positions.find((position) => position.symbol.toUpperCase() === symbol.toUpperCase())
    : null;

  let positionValueAfter: number | null = null;
  let estAvgCost: number | null = null;

  if (existingPosition) {
    const existingQty = existingPosition.quantity;
    const existingAvg = existingPosition.avg_entry_price;

    if (isBuy) {
      const newTotalQty = existingQty + quantity;
      positionValueAfter = newTotalQty * price;
      estAvgCost =
        newTotalQty > 0
          ? (existingQty * existingAvg + quantity * price) / newTotalQty
          : null;
    } else {
      const newTotalQty = existingQty - quantity;
      positionValueAfter = newTotalQty > 0 ? newTotalQty * price : 0;
      estAvgCost = newTotalQty > 0 ? existingAvg : null;
    }
  } else if (isBuy) {
    positionValueAfter = cost;
    estAvgCost = price;
  }

  const riskColor =
    portfolioPct == null
      ? "text-muted-foreground"
      : portfolioPct > 15
        ? "text-red-300"
        : portfolioPct > 5
          ? "text-amber-300"
          : "text-emerald-300";

  const riskLabel =
    portfolioPct == null
      ? null
      : portfolioPct > 15
        ? "Large position relative to portfolio"
        : portfolioPct > 5
          ? "Moderate position size"
          : "Contained position size";

  return (
    <div className="app-inset space-y-2.5 px-3.5 py-3">
      <div className="app-label">Order Preview</div>

      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">
          {isBuy ? "Estimated Cost" : "Estimated Proceeds"}
        </span>
        <span className="font-mono font-medium tabular-nums">${fmt(cost)}</span>
      </div>

      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">Remaining Cash</span>
        <span
          className={`font-mono font-medium tabular-nums ${
            remainingCash < 0 ? "text-red-300" : ""
          }`}
        >
          ${fmt(remainingCash)}
        </span>
      </div>

      {portfolioPct != null && (
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Portfolio Impact</span>
          <span className={`font-mono font-medium tabular-nums ${riskColor}`}>
            {portfolioPct.toFixed(1)}%
          </span>
        </div>
      )}

      {positionValueAfter != null && (
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Position Value After</span>
          <span className="font-mono font-medium tabular-nums">
            ${fmt(positionValueAfter)}
          </span>
        </div>
      )}

      {estAvgCost != null && existingPosition && (
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Estimated Avg Cost</span>
          <span className="font-mono font-medium tabular-nums">
            ${fmt(estAvgCost)}
          </span>
        </div>
      )}

      {portfolioPct != null && (
        <div className={`border-t border-border/60 pt-2 text-[11px] ${riskColor}`}>
          This order would consume {portfolioPct.toFixed(1)}% of the portfolio.
          <span className="mt-0.5 block font-medium">{riskLabel}</span>
        </div>
      )}
    </div>
  );
}
