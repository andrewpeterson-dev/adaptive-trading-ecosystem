'use client';

import type { TradeSignal } from '@/types/copilot';

interface TradeSignalCardProps {
  signal: TradeSignal;
}

export function TradeSignalCard({ signal }: TradeSignalCardProps) {
  const actionColors: Record<string, string> = {
    buy: 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20',
    sell: 'text-red-500 bg-red-500/10 border-red-500/20',
    hold: 'text-amber-500 bg-amber-500/10 border-amber-500/20',
    review: 'text-blue-500 bg-blue-500/10 border-blue-500/20',
  };

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-foreground">{signal.symbol}</span>
          <span className={`text-xs font-medium px-1.5 py-0.5 rounded border ${actionColors[signal.action] || ''}`}>
            {signal.action.toUpperCase()}
          </span>
        </div>
        <div className="text-xs text-muted-foreground">
          {(signal.confidence * 100).toFixed(0)}% confidence
        </div>
      </div>

      <div className="text-xs text-muted-foreground">{signal.strategyType.replace(/_/g, ' ')}</div>

      {signal.thesis.length > 0 && (
        <div className="space-y-0.5">
          <span className="text-xs font-medium text-foreground">Thesis:</span>
          {signal.thesis.map((t, i) => (
            <p key={i} className="text-xs text-muted-foreground pl-2">- {t}</p>
          ))}
        </div>
      )}

      {signal.risks.length > 0 && (
        <div className="space-y-0.5">
          <span className="text-xs font-medium text-red-400">Risks:</span>
          {signal.risks.map((r, i) => (
            <p key={i} className="text-xs text-muted-foreground pl-2">- {r}</p>
          ))}
        </div>
      )}

      <div className="flex gap-3 text-xs text-muted-foreground">
        <span>Entry: {signal.entry.type} @ ${signal.entry.price}</span>
        <span>TP: ${signal.exitPlan.takeProfit}</span>
        <span>SL: ${signal.exitPlan.stopLoss}</span>
      </div>
    </div>
  );
}
