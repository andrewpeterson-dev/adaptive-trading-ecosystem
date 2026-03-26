"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Loader2, TrendingUp } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { useTradingMode } from "@/hooks/useTradingMode";
import type { Position } from "@/types/trading";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Surface,
  SurfaceBody,
  SurfaceHeader,
  SurfaceTitle,
} from "@/components/ui/surface";

interface HoldingsTableProps {
  onTickersReady?: (tickers: string[]) => void;
}

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPnl(value: number): string {
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}${formatCurrency(value)}`;
}

function formatPnlPct(value: number): string {
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}${(value * 100).toFixed(2)}%`;
}

function pnlColor(value: number): string {
  return value >= 0 ? "text-emerald-400" : "text-red-400";
}

const COLUMNS = ["Symbol", "Qty", "Avg Entry", "Current", "Mkt Value", "P&L", "Change %"] as const;

export function HoldingsTable({ onTickersReady }: HoldingsTableProps) {
  const { mode } = useTradingMode();
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPositions = useCallback(async () => {
    try {
      const data = await apiFetch<{ positions: Position[] }>(
        `/api/trading/positions?mode=${mode}`,
      );
      const pos = data.positions || [];
      setPositions(pos);
      if (onTickersReady && pos.length > 0) {
        const tickers = [...new Set(pos.map((p) => p.symbol))];
        onTickersReady(tickers);
      }
    } catch {
      setPositions([]);
    } finally {
      setLoading(false);
    }
  }, [mode, onTickersReady]);

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  return (
    <Surface>
      <SurfaceHeader>
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
          <SurfaceTitle>Holdings</SurfaceTitle>
          {positions.length > 0 && (
            <span className="rounded-full bg-muted/50 px-2 py-0.5 text-[10px] font-mono text-muted-foreground">
              {positions.length}
            </span>
          )}
        </div>
      </SurfaceHeader>
      <SurfaceBody>
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : positions.length === 0 ? (
          <EmptyState
            className="py-10"
            icon={<TrendingUp className="h-4 w-4 text-muted-foreground" />}
            title="No holdings"
            description="Open positions will appear here"
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="app-table app-table-compact">
              <thead>
                <tr>
                  {COLUMNS.map((col) => (
                    <th key={col} className="whitespace-nowrap">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => {
                  const pnl = p.unrealized_pnl ?? 0;
                  const pnlPct = p.unrealized_pnl_pct ?? 0;
                  const color = pnlColor(pnl);
                  return (
                    <tr key={p.contract_symbol || p.symbol} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 px-4 font-mono font-bold text-sm">{p.symbol}</td>
                      <td className="py-2.5 px-4 font-mono tabular-nums">{Math.abs(p.quantity)}</td>
                      <td className="py-2.5 px-4 font-mono tabular-nums">{formatCurrency(p.avg_entry_price)}</td>
                      <td className="py-2.5 px-4 font-mono tabular-nums">{formatCurrency(p.current_price)}</td>
                      <td className="py-2.5 px-4 font-mono tabular-nums">{formatCurrency(p.market_value)}</td>
                      <td className={`py-2.5 px-4 font-mono tabular-nums font-medium ${color}`}>
                        {p.unrealized_pnl != null ? formatPnl(pnl) : "\u2014"}
                      </td>
                      <td className={`py-2.5 px-4 font-mono tabular-nums font-medium ${color}`}>
                        {p.unrealized_pnl_pct != null ? formatPnlPct(pnlPct) : "\u2014"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </SurfaceBody>
    </Surface>
  );
}
