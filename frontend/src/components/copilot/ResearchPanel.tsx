'use client';

export function ResearchPanel() {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground px-4">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-2 opacity-50">
        <circle cx="11" cy="11" r="8" />
        <path d="M21 21l-4.35-4.35" />
      </svg>
      <p className="text-sm font-medium">Research</p>
      <p className="text-xs mt-1">Upload documents, search financial data, and get AI-powered research summaries.</p>
    </div>
  );
}
