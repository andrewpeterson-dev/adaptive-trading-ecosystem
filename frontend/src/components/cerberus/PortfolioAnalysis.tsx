'use client';

import { useState } from 'react';
import { sendChatMessage } from '@/lib/cerberus-api';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useUIContextStore } from '@/stores/ui-context-store';

export function PortfolioAnalysis() {
  const [isLoading, setIsLoading] = useState(false);
  const { addMessage, activeThreadId, setActiveThread } = useCerberusStore();
  const { pageContext } = useUIContextStore();

  const quickActions = [
    { label: 'Portfolio Risk', prompt: 'Analyze my portfolio risk including VaR, drawdown, and concentration' },
    { label: 'Best Trades', prompt: 'Show me my best performing trades' },
    { label: 'Worst Trades', prompt: 'Show me my worst trades and what went wrong' },
    { label: 'Exposure', prompt: 'What is my current portfolio exposure by sector and asset type?' },
    { label: 'Performance', prompt: 'Compare my strategy performance across all strategies' },
    { label: 'Holdings', prompt: 'Show my current positions and unrealized P&L' },
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
        mode: 'portfolio',
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
      console.error('Portfolio analysis error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-1">Portfolio Analysis</h3>
        <p className="text-xs text-muted-foreground">Quick AI-powered insights into your portfolio.</p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {quickActions.map((action) => (
          <button
            key={action.label}
            onClick={() => handleAction(action.prompt)}
            disabled={isLoading}
            className="text-left px-3 py-2.5 rounded-lg border border-border hover:bg-muted hover:border-primary/30 transition-all text-xs font-medium text-foreground disabled:opacity-50"
          >
            {action.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-4">
          <div className="flex space-x-1">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      )}
    </div>
  );
}
