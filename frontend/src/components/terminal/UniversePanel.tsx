"use client";
import { Globe } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";

interface UniversePanelProps {
  symbols: string[];
  activeSymbol: string;
  onSymbolSelect: (symbol: string) => void;
  openPositionSymbols?: string[];
}

export function UniversePanel({ symbols, activeSymbol, onSymbolSelect, openPositionSymbols = [] }: UniversePanelProps) {
  return (
    <TerminalPanel title="Universe" icon={<Globe className="h-3.5 w-3.5" />} accent="text-cyan-400" compact>
      <div className="flex flex-wrap gap-1.5">
        {symbols.map((symbol) => {
          const isActive = activeSymbol === symbol;
          const hasPosition = openPositionSymbols.includes(symbol);
          return (
            <button
              key={symbol}
              type="button"
              onClick={() => onSymbolSelect(symbol)}
              className={`rounded-lg border px-2.5 py-1 text-[11px] font-semibold tracking-wide transition-all ${
                isActive
                  ? "border-sky-400/50 bg-sky-400/15 text-sky-400 shadow-[0_0_8px_-3px_rgba(56,189,248,0.4)]"
                  : hasPosition
                    ? "border-emerald-400/30 bg-emerald-400/8 text-emerald-400"
                    : "border-border/50 bg-muted/15 text-muted-foreground hover:text-foreground hover:border-border"
              }`}
            >
              {hasPosition && <span className="mr-1">&#9679;</span>}
              {symbol}
            </button>
          );
        })}
      </div>
    </TerminalPanel>
  );
}
