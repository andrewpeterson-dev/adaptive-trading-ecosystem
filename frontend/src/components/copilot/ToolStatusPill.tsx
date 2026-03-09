'use client';

import type { ToolCallEvent } from '@/types/copilot';

interface ToolStatusPillProps {
  toolCall: ToolCallEvent;
}

const STATUS_STYLES: Record<string, string> = {
  pending: 'bg-muted text-muted-foreground',
  running: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  completed: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
  failed: 'bg-red-500/10 text-red-500 border-red-500/20',
};

export function ToolStatusPill({ toolCall }: ToolStatusPillProps) {
  const style = STATUS_STYLES[toolCall.status] || STATUS_STYLES.pending;

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>
      {toolCall.status === 'running' && (
        <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      )}
      {toolCall.toolName}
    </span>
  );
}
