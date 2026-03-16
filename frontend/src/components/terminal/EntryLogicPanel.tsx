"use client";
import { Zap } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";

interface EntryLogicPanelProps {
  conditions: Array<Record<string, unknown>>;
  exitConditions: Array<Record<string, unknown>>;
  stopLossPct?: number;
  takeProfitPct?: number;
}

function formatCondition(c: Record<string, unknown>): string {
  const ind = String(c.indicator ?? "").toUpperCase();
  const params = (c.params ?? {}) as Record<string, unknown>;
  const period = params.period ? `(${params.period})` : "";
  const field = c.field ? `.${c.field}` : "";
  const op = String(c.operator ?? ">").replace("crosses_above", "crosses above").replace("crosses_below", "crosses below");
  const val = c.compare_to === "PRICE" ? "Price" : String(c.value ?? 0);
  return `${ind}${field}${period} ${op} ${val}`;
}

export function EntryLogicPanel({ conditions, exitConditions, stopLossPct, takeProfitPct }: EntryLogicPanelProps) {
  return (
    <TerminalPanel title="Entry & Exit Logic" icon={<Zap className="h-3.5 w-3.5" />} accent="text-violet-400" compact>
      <div className="space-y-3">
        <div>
          <div className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/60 mb-1.5">Entry signals</div>
          {conditions.map((c, i) => (
            <div key={i} className="flex items-start gap-2 py-0.5 text-xs text-foreground">
              <span className="text-emerald-400 mt-0.5">&#9679;</span>
              <span>{(c.description as string) || formatCondition(c)}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/60 mb-1.5">Exit signals</div>
          {exitConditions.map((c, i) => (
            <div key={i} className="flex items-start gap-2 py-0.5 text-xs text-foreground">
              <span className="text-rose-400 mt-0.5">&#9679;</span>
              <span>{(c.description as string) || formatCondition(c)}</span>
            </div>
          ))}
          {stopLossPct != null && stopLossPct > 0 && (
            <div className="flex items-start gap-2 py-0.5 text-xs text-foreground">
              <span className="text-rose-400 mt-0.5">&#9679;</span>
              <span>Stop loss <strong>{(stopLossPct * 100).toFixed(1)}%</strong></span>
            </div>
          )}
          {takeProfitPct != null && takeProfitPct > 0 && (
            <div className="flex items-start gap-2 py-0.5 text-xs text-foreground">
              <span className="text-emerald-400 mt-0.5">&#9679;</span>
              <span>Take profit <strong>{(takeProfitPct * 100).toFixed(1)}%</strong></span>
            </div>
          )}
        </div>
      </div>
    </TerminalPanel>
  );
}
