'use client';

import { useState } from 'react';
import { useCopilotStore } from '@/stores/copilot-store';
import { sendChatMessage } from '@/lib/copilot-api';
import { useUIContextStore } from '@/stores/ui-context-store';

export function StrategyBuilder() {
  const [strategyPrompt, setStrategyPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const { addMessage, activeThreadId, setActiveThread } = useCopilotStore();
  const { pageContext } = useUIContextStore();

  const handleGenerate = async () => {
    if (!strategyPrompt.trim() || isGenerating) return;
    setIsGenerating(true);

    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      contentMd: strategyPrompt,
      structuredJson: null,
      modelName: null,
      citations: [],
      toolCalls: [],
      createdAt: new Date().toISOString(),
    });

    try {
      const response = await sendChatMessage({
        threadId: activeThreadId || undefined,
        mode: 'strategy',
        message: strategyPrompt,
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
      console.error('Strategy generation error:', error);
    } finally {
      setIsGenerating(false);
      setStrategyPrompt('');
    }
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-1">AI Strategy Builder</h3>
        <p className="text-xs text-muted-foreground">Describe a trading strategy and the AI will help you build, test, and deploy it.</p>
      </div>

      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          {['Covered call on NVDA', 'Momentum scalper', 'Mean reversion on SPY', 'Iron condor strategy'].map((preset) => (
            <button
              key={preset}
              onClick={() => setStrategyPrompt(preset)}
              className="text-xs px-2.5 py-1.5 rounded-md border border-border hover:bg-muted transition-colors text-left text-muted-foreground"
            >
              {preset}
            </button>
          ))}
        </div>

        <textarea
          value={strategyPrompt}
          onChange={(e) => setStrategyPrompt(e.target.value)}
          placeholder="Describe your strategy idea..."
          rows={4}
          className="w-full resize-none rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
        />

        <button
          onClick={handleGenerate}
          disabled={!strategyPrompt.trim() || isGenerating}
          className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {isGenerating ? 'Generating...' : 'Generate Strategy'}
        </button>
      </div>
    </div>
  );
}
