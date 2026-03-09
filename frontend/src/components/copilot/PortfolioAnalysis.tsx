'use client';

export function PortfolioAnalysis() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground px-4">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-2 opacity-50">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 2a10 10 0 0 1 10 10h-10z" />
      </svg>
      <p className="text-sm font-medium">Portfolio Analysis</p>
      <p className="text-xs mt-1">AI-driven portfolio insights, risk analysis, and rebalancing suggestions.</p>
    </div>
  );
}
