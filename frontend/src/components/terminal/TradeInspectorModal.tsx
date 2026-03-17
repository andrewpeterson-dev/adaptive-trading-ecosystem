"use client";
import { useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import type { BotTrade } from "@/lib/cerberus-api";
import { formatCurrency, formatPercent, formatProbability, formatDateTime } from "@/lib/bot-visualization";

interface TradeInspectorModalProps {
  trade: BotTrade | null;
  config: Record<string, unknown>;
  onClose: () => void;
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className={`text-sm font-semibold font-mono ${color ?? "text-foreground"}`}>{value}</span>
    </div>
  );
}

function SideBadge({ side }: { side: string }) {
  const isBuy = side.toLowerCase().startsWith("buy");
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
        isBuy ? "bg-emerald-400/15 text-emerald-400" : "bg-rose-400/15 text-rose-400"
      }`}
    >
      {side}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const isOpen = status.toLowerCase() === "open";
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
        isOpen ? "bg-sky-400/15 text-sky-400" : "bg-muted/40 text-muted-foreground"
      }`}
    >
      {status}
    </span>
  );
}

export function TradeInspectorModal({ trade, config, onClose }: TradeInspectorModalProps) {
  useEffect(() => {
    if (!trade) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [trade, onClose]);

  if (!trade) return null;

  const isOpen = trade.status.toLowerCase() === "open";
  const pnl = trade.netPnl ?? trade.grossPnl;
  const pnlColor = pnl != null ? (pnl >= 0 ? "text-emerald-400" : "text-rose-400") : undefined;
  const returnPct = trade.returnPct;
  const returnColor = returnPct != null ? (returnPct >= 0 ? "text-emerald-400" : "text-rose-400") : undefined;

  const stopLossPct = config.stop_loss_pct as number | null | undefined;
  const takeProfitPct = config.take_profit_pct as number | null | undefined;

  const explanation = trade.botExplanation || (trade.reasons && trade.reasons.length > 0 ? trade.reasons.join("; ") : null);

  const riskLabel = trade.riskAssessment ?? "N/A";

  const modal = (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Panel */}
      <div
        className="relative z-10 w-full max-w-lg mx-4 rounded-2xl border border-border/60 bg-card/95 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/40 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <span className="text-base font-bold text-foreground">{trade.symbol}</span>
            <SideBadge side={trade.side} />
            <StatusBadge status={trade.status} />
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4 space-y-5">
          {/* Price & P/L grid */}
          <div className="grid grid-cols-3 gap-4">
            <Metric label="Entry Price" value={formatCurrency(trade.entryPrice)} />
            {isOpen ? (
              <Metric label="Current Price" value="Live" color="text-sky-400" />
            ) : (
              <Metric label="Exit Price" value={formatCurrency(trade.exitPrice)} />
            )}
            <Metric label="Quantity" value={String(trade.quantity)} />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <Metric label="P&L" value={formatCurrency(pnl)} color={pnlColor} />
            <Metric label="Return" value={formatPercent(returnPct, 2, true)} color={returnColor} />
            <Metric label="AI Confidence" value={formatProbability(trade.probabilityScore)} />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Metric label="Risk Assessment" value={riskLabel} />
            {trade.strategyTag && <Metric label="Strategy" value={trade.strategyTag} />}
          </div>

          {/* Timestamps */}
          <div className="grid grid-cols-2 gap-4 border-t border-border/30 pt-4">
            <Metric label="Entry Time" value={formatDateTime(trade.entryTs ?? trade.createdAt)} />
            {!isOpen && <Metric label="Exit Time" value={formatDateTime(trade.exitTs)} />}
          </div>

          {/* Entry Reason */}
          {explanation && (
            <div className="border-t border-border/30 pt-4">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Entry Reason</span>
              <p className="mt-1.5 text-xs leading-relaxed text-foreground/80">{explanation}</p>
            </div>
          )}

          {/* Indicator Signals */}
          {trade.indicatorSignals && trade.indicatorSignals.length > 0 && (
            <div className="border-t border-border/30 pt-4">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Indicator Signals</span>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {trade.indicatorSignals.map((signal) => (
                  <span key={signal} className="rounded-md bg-muted/30 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                    {signal}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Exit Conditions */}
          {(stopLossPct != null || takeProfitPct != null || trade.stopLossPrice != null || trade.takeProfitPrice != null) && (
            <div className="border-t border-border/30 pt-4">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Exit Conditions</span>
              <div className="mt-1.5 grid grid-cols-2 gap-3">
                {trade.stopLossPrice != null && (
                  <Metric label="Stop Loss Price" value={formatCurrency(trade.stopLossPrice)} color="text-rose-400" />
                )}
                {trade.takeProfitPrice != null && (
                  <Metric label="Take Profit Price" value={formatCurrency(trade.takeProfitPrice)} color="text-emerald-400" />
                )}
                {stopLossPct != null && trade.stopLossPrice == null && (
                  <Metric label="Stop Loss %" value={formatPercent(stopLossPct, 1, true)} color="text-rose-400" />
                )}
                {takeProfitPct != null && trade.takeProfitPrice == null && (
                  <Metric label="Take Profit %" value={formatPercent(takeProfitPct, 1, true)} color="text-emerald-400" />
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
