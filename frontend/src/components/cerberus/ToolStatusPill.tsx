'use client';

import type { ToolCallEvent } from '@/types/cerberus';

interface ToolStatusPillProps {
  toolCall: ToolCallEvent;
}

export function ToolStatusPill({ toolCall }: ToolStatusPillProps) {
  const statusStyles: Record<string, string> = {
    pending: 'bg-muted text-muted-foreground',
    running: 'bg-primary/10 text-primary border-primary/20 animate-pulse',
    completed: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
    failed: 'bg-red-500/10 text-red-500 border-red-500/20',
  };

  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full border ${statusStyles[toolCall.status] || statusStyles.pending}`}>
      {toolCall.status === 'running' && (
        <svg className="w-2.5 h-2.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
          <circle cx="12" cy="12" r="10" strokeDasharray="60" strokeDashoffset="20" />
        </svg>
      )}
      {toolCall.toolName}
      {toolCall.latencyMs !== undefined && toolCall.status === 'completed' && (
        <span className="opacity-60">{toolCall.latencyMs}ms</span>
      )}
    </span>
  );
}
