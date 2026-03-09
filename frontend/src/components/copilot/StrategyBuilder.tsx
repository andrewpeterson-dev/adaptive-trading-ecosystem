'use client';

export function StrategyBuilder() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground px-4">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-2 opacity-50">
        <path d="M3 3v18h18" />
        <path d="M7 16l4-8 4 4 4-8" />
      </svg>
      <p className="text-sm font-medium">Strategy Builder</p>
      <p className="text-xs mt-1">Build, backtest, and deploy trading strategies with AI assistance.</p>
    </div>
  );
}
