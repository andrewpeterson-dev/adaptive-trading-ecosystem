"use client";

import React, { useState } from "react";
import { Loader2, X } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { Position } from "@/types/trading";

interface PositionCardProps {
  position: Position;
  onClose: () => void;
}

export function PositionCard({ position, onClose }: PositionCardProps) {
  const [closing, setClosing] = useState(false);

  const isProfit = (position.unrealized_pnl ?? 0) >= 0;
  const pnlColor = isProfit ? "text-emerald-400" : "text-red-400";

  const handleClose = async () => {
    setClosing(true);
    try {
      await apiFetch("/api/trading/execute", {
        method: "POST",
        body: JSON.stringify({
          symbol: position.symbol,
          direction: position.side === "long" ? "short" : "long",
          quantity: Math.abs(position.quantity),
          strength: 1.0,
          model_name: "manual",
          order_type: "market",
          limit_price: position.current_price,
          user_confirmed: true,
        }),
      });
      onClose();
    } catch {
      // silent fail — refresh will show updated state
    } finally {
      setClosing(false);
    }
  };

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-mono font-semibold text-sm">{position.symbol}</span>
          <span
            className={`text-xs font-medium px-1.5 py-0.5 rounded ${
              position.side === "long"
                ? "text-emerald-400 bg-emerald-400/10"
                : "text-red-400 bg-red-400/10"
            }`}
          >
            {position.side?.toUpperCase() || "LONG"}
          </span>
        </div>
        <button
          onClick={handleClose}
          disabled={closing}
          className="text-xs text-muted-foreground hover:text-foreground border border-transparent hover:border-border/50 rounded-md px-2 py-1 transition-colors flex items-center gap-1"
        >
          {closing ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <X className="h-3 w-3" />
          )}
          Close
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <div className="text-muted-foreground">Qty</div>
          <div className="font-mono font-medium">{position.quantity}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Avg Entry</div>
          <div className="font-mono font-medium">${position.avg_entry_price?.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Current Price</div>
          <div className="font-mono font-medium">${position.current_price?.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-muted-foreground">Market Value</div>
          <div className="font-mono font-medium">
            ${(position.market_value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
      </div>

      <div className="pt-2 border-t border-border/30 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">Unrealized P&L</span>
        <div className="text-right">
          <span className={`font-mono font-semibold text-sm ${pnlColor}`}>
            {isProfit ? "+" : ""}${(position.unrealized_pnl ?? 0).toFixed(2)}
          </span>
          <span className={`text-xs ml-1.5 ${pnlColor}`}>
            ({isProfit ? "+" : ""}{((position.unrealized_pnl_pct ?? 0) * 100).toFixed(1)}%)
          </span>
        </div>
      </div>
    </div>
  );
}
