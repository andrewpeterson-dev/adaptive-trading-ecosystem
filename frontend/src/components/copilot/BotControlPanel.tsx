'use client';

import { useState } from 'react';
import { sendChatMessage } from '@/lib/copilot-api';
import { useCopilotStore } from '@/stores/copilot-store';
import { useUIContextStore } from '@/stores/ui-context-store';

export function BotControlPanel() {
  const [isLoading, setIsLoading] = useState(false);
  const { addMessage, activeThreadId, setActiveThread } = useCopilotStore();
  const { pageContext } = useUIContextStore();

  const actions = [
    { label: 'List Bots', prompt: 'List all my trading bots and their current status' },
    { label: 'Bot Performance', prompt: 'Show performance metrics for all my active bots' },
    { label: 'Create Bot', prompt: 'Help me create a new trading bot' },
    { label: 'Stop All', prompt: 'Show me which bots are active so I can decide which to stop' },
  ];

  const handleAction = async (prompt: string) => {
    if (isLoading) return;
    setIsLoading(true);

    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      contentMd: prompt,
      structuredJson: null,
      modelName: null,
      citations: [],
      toolCalls: [],
      createdAt: new Date().toISOString(),
    });

    try {
      const response = await sendChatMessage({
        threadId: activeThreadId || undefined,
        mode: 'bot_control',
        message: prompt,
        pageContext,
      });
      if (!activeThreadId) setActiveThread(response.threadId);
      if (response.message) {
        addMessage({
          id: response.turnId,
          role: 'assistant',
          contentMd: response.message.markdown || '',
          structuredJson: response.message,
          modelName: null,
          citations: response.message.citations || [],
          toolCalls: [],
          createdAt: new Date().toISOString(),
        });
      }
    } catch (error) {
      console.error('Bot control error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-1">Bot Control</h3>
        <p className="text-xs text-muted-foreground">Manage your AI trading bots.</p>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {actions.map((a) => (
          <button
            key={a.label}
            onClick={() => handleAction(a.prompt)}
            disabled={isLoading}
            className="text-left px-3 py-2.5 rounded-lg border border-border hover:bg-muted hover:border-primary/30 transition-all text-xs font-medium text-foreground disabled:opacity-50"
          >
            {a.label}
          </button>
        ))}
      </div>
    </div>
  );
}
