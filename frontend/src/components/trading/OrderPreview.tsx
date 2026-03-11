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

export function OrderPreview({ quantity, price, direction, symbol }: OrderPreviewProps) {
  const { account, positions } = useTradeStore();

  if (quantity <= 0 || price == null || price <= 0 || !account) return null;

  const cost = quantity * price;
  const isBuy = direction === "buy";
  const remainingCash = isBuy ? account.cash - cost : account.cash + cost;
  const portfolioPct =
    account.portfolio_value > 0 ? (cost / account.portfolio_value) * 100 : null;

  // Existing position lookup
  const existingPosition = symbol
    ? positions.find(
        (p) => p.symbol.toUpperCase() === symbol.toUpperCase()
      )
    : null;

  // Position value after this order
  let positionValueAfter: number | null = null;
  let estAvgCost: number | null = null;

  if (existingPosition) {
    const existingQty = existingPosition.quantity;
    const existingAvg = existingPosition.avg_entry_price;
    const existingValue = existingQty * (existingPosition.current_price || existingAvg);

    if (isBuy) {
      const newTotalQty = existingQty + quantity;
      positionValueAfter = newTotalQty * price;
      // Weighted average cost
      estAvgCost =
        newTotalQty > 0
          ? (existingQty * existingAvg + quantity * price) / newTotalQty
          : null;
    } else {
      const newTotalQty = existingQty - quantity;
      positionValueAfter = newTotalQty > 0 ? newTotalQty * price : 0;
      // Avg cost doesn't change when selling
      estAvgCost = newTotalQty > 0 ? existingAvg : null;
    }
  } else if (isBuy) {
    positionValueAfter = cost;
    estAvgCost = price;
  }

  // Risk color for portfolio percentage
  const riskColor =
    portfolioPct == null
      ? "text-muted-foreground"
      : portfolioPct > 15
        ? "text-red-400"
        : portfolioPct > 5
          ? "text-amber-400"
          : "text-emerald-400";

  const riskLabel =
    portfolioPct == null
      ? null
      : portfolioPct > 15
        ? "Large position relative to portfolio"
        : portfolioPct > 5
          ? "Moderate position size"
          : null;

  return (
    <div className="rounded-md border border-border/50 bg-muted/30 px-3 py-2.5 space-y-1.5">
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1">
        Order Preview
      </div>

      {/* Est. Cost */}
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">
          {isBuy ? "Est. Cost" : "Est. Proceeds"}
        </span>
        <span className="font-mono tabular-nums font-medium">${fmt(cost)}</span>
      </div>

      {/* Remaining Cash */}
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">Remaining Cash</span>
        <span
          className={`font-mono tabular-nums font-medium ${
            remainingCash < 0 ? "text-red-400" : ""
          }`}
        >
          ${fmt(remainingCash)}
        </span>
      </div>

      {/* % of Portfolio */}
      {portfolioPct != null && (
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">% of Portfolio</span>
          <span className={`font-mono tabular-nums font-medium ${riskColor}`}>
            {portfolioPct.toFixed(1)}%
          </span>
        </div>
      )}

      {/* Position Value After */}
      {positionValueAfter != null && (
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Position Value After</span>
          <span className="font-mono tabular-nums font-medium">
            ${fmt(positionValueAfter)}
          </span>
        </div>
      )}

      {/* Est. Avg Cost */}
      {estAvgCost != null && existingPosition && (
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Est. Avg Cost</span>
          <span className="font-mono tabular-nums font-medium">
            ${fmt(estAvgCost)}
          </span>
        </div>
      )}

      {/* Risk Summary */}
      {portfolioPct != null && (
        <div className={`text-[10px] pt-1 ${riskColor}`}>
          This would be {portfolioPct.toFixed(1)}% of your portfolio
          {riskLabel && <span className="block mt-0.5 font-medium">{riskLabel}</span>}
        </div>
      )}
    </div>
  );
}
