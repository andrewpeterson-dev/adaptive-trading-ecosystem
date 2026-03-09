'use client';

export function BotControlPanel() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground px-4">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-2 opacity-50">
        <rect x="3" y="11" width="18" height="10" rx="2" />
        <circle cx="9" cy="16" r="1" />
        <circle cx="15" cy="16" r="1" />
        <path d="M8 11V7a4 4 0 0 1 8 0v4" />
      </svg>
      <p className="text-sm font-medium">Bot Control</p>
      <p className="text-xs mt-1">Manage, monitor, and configure your automated trading bots.</p>
    </div>
  );
}
