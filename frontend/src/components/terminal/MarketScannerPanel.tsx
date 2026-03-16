"use client";
import { Radar } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";

interface MarketScannerPanelProps {
  symbols: string[];
  trades: Array<{ symbol: string; side: string; status: string; entryPrice?: number | null }>;
  conditions: Array<Record<string, unknown>>;
}

interface SymbolSignal {
  symbol: string;
  description: string;
  strength: "high" | "moderate" | "low";
  isActive: boolean;
}

function deriveSignals(
  symbols: string[],
  trades: MarketScannerPanelProps["trades"],
  conditions: Array<Record<string, unknown>>,
): SymbolSignal[] {
  const openTradeMap = new Map<string, MarketScannerPanelProps["trades"][number]>();
  for (const trade of trades) {
    if (trade.status.toLowerCase() === "open") {
      openTradeMap.set(trade.symbol.toUpperCase(), trade);
    }
  }

  const conditionMap = new Map<string, string>();
  for (const cond of conditions) {
    const indicator = typeof cond.indicator === "string" ? cond.indicator : null;
    const condSymbols = Array.isArray(cond.symbols) ? cond.symbols : [];
    const desc = indicator
      ? indicator.replace(/_/g, " ").replace(/\b\w/g, (m: string) => m.toUpperCase())
      : null;
    if (desc) {
      for (const s of condSymbols) {
        if (typeof s === "string") conditionMap.set(s.toUpperCase(), desc);
      }
    }
  }

  return symbols.map((symbol) => {
    const upper = symbol.toUpperCase();
    const openTrade = openTradeMap.get(upper);
    const hasClosedTrades = trades.some(
      (t) => t.symbol.toUpperCase() === upper && t.status.toLowerCase() !== "open",
    );

    if (openTrade) {
      const sideLabel = openTrade.side.toLowerCase().startsWith("buy") ? "Long" : "Short";
      const matchDesc = conditionMap.get(upper) || `${sideLabel} Position`;
      return { symbol: upper, description: matchDesc, strength: "high" as const, isActive: true };
    }

    if (hasClosedTrades || conditionMap.has(upper)) {
      const desc = conditionMap.get(upper) || "Near threshold";
      return { symbol: upper, description: desc, strength: "moderate" as const, isActive: false };
    }

    return { symbol: upper, description: "Monitoring", strength: "low" as const, isActive: false };
  });
}

function SignalRow({ signal }: { signal: SymbolSignal }) {
  const strengthStyles = {
    high: "text-emerald-400",
    moderate: "text-amber-400",
    low: "text-muted-foreground",
  };

  const dotStyles = {
    high: "text-emerald-400",
    moderate: "text-amber-400",
    low: "text-muted-foreground/50",
  };

  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
      <div className="flex items-center gap-2">
        <span className={`text-xs font-bold font-mono ${strengthStyles[signal.strength]}`}>
          {signal.symbol}
        </span>
        <span className="text-[10px] text-muted-foreground">{signal.description}</span>
      </div>
      <div className="flex items-center gap-1.5">
        {signal.isActive && (
          <span className="text-[10px] font-semibold text-emerald-400">Active</span>
        )}
        <span className={`text-xs ${dotStyles[signal.strength]}`}>
          {signal.strength === "high" ? "\u25CF" : signal.strength === "moderate" ? "\u25D0" : "\u2013"}
        </span>
      </div>
    </div>
  );
}

export function MarketScannerPanel({ symbols, trades, conditions }: MarketScannerPanelProps) {
  const signals = deriveSignals(symbols, trades, conditions);
  const strongSignals = signals.filter((s) => s.strength === "high");
  const otherSignals = signals.filter((s) => s.strength !== "high");

  return (
    <TerminalPanel title="AI Market Scanner" icon={<Radar className="h-3.5 w-3.5" />} accent="text-violet-400" compact>
      <div className="mb-3">
        <span className="text-[10px] text-muted-foreground">
          Watching: <span className="font-semibold text-foreground">{symbols.length}</span> symbols
        </span>
      </div>

      {strongSignals.length > 0 && (
        <div className="mb-3">
          <span className="text-[10px] uppercase tracking-wider font-semibold text-emerald-400/80 mb-1 block">
            Strong Signals
          </span>
          {strongSignals.map((signal) => (
            <SignalRow key={signal.symbol} signal={signal} />
          ))}
        </div>
      )}

      {otherSignals.length > 0 && (
        <div>
          <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground/80 mb-1 block">
            Scanning
          </span>
          {otherSignals.map((signal) => (
            <SignalRow key={signal.symbol} signal={signal} />
          ))}
        </div>
      )}

      {signals.length === 0 && (
        <span className="text-xs text-muted-foreground">No symbols configured</span>
      )}
    </TerminalPanel>
  );
}
