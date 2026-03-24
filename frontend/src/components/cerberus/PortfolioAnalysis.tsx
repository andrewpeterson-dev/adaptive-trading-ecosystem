'use client';

import Link from 'next/link';
import { useState } from 'react';
import { LineChart, PlugZap, ShieldCheck } from 'lucide-react';
import { sendChatMessage } from '@/lib/cerberus-api';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useUIContextStore } from '@/stores/ui-context-store';
import { useTradingMode } from '@/hooks/useTradingMode';
import { useCerberusWorkspaceStatus } from '@/hooks/useCerberusWorkspaceStatus';
import { EmptyState } from '@/components/ui/empty-state';

export function PortfolioAnalysis() {
  const [isLoading, setIsLoading] = useState(false);
  const { addMessage, activeThreadId, setActiveThread, setActiveTab } = useCerberusStore();
  const { pageContext } = useUIContextStore();
  const { mode } = useTradingMode();
  const { status, loading } = useCerberusWorkspaceStatus(mode);

  const quickActions = [
    {
      label: 'Risk Review',
      description: 'VaR, drawdown, concentration, and position sizing pressure.',
      prompt: 'Analyze my portfolio risk including VaR, drawdown, and concentration',
    },
    {
      label: 'Performance Review',
      description: 'Realized winners, losers, and consistency across recent trades.',
      prompt: 'Review recent portfolio performance, including best trades, worst trades, and consistency',
    },
    {
      label: 'Exposure Map',
      description: 'Sector, symbol, and asset-class exposure in the current book.',
      prompt: 'What is my current portfolio exposure by sector, symbol, and asset type?',
    },
    {
      label: 'Current Holdings',
      description: 'Open positions, unrealized P&L, and risk hotspots.',
      prompt: 'Show my current positions and unrealized P&L',
    },
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

    setActiveTab('chat');

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
      const detail = error instanceof Error ? error.message : 'Analysis request failed';
      addMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        contentMd: `Portfolio analysis failed: ${detail}`,
        structuredJson: null,
        modelName: null,
        citations: [],
        toolCalls: [],
        createdAt: new Date().toISOString(),
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-y-auto p-4 space-y-4">
      <div className="space-y-1">
        <h3 className="text-sm font-semibold text-foreground">Portfolio Analysis</h3>
        <p className="text-xs text-muted-foreground">
          Cerberus can review holdings, exposure, and realized trade quality once a broker is connected.
        </p>
      </div>

      {!loading && !status?.portfolioConnected && (
        <EmptyState
          icon={<PlugZap className="h-5 w-5 text-muted-foreground" />}
          title="Portfolio connection required"
          description={status?.connectedData.find((item) => item.key === 'portfolio_holdings')?.detail}
          action={
            <Link href="/settings" className="app-button-primary">
              Connect data
            </Link>
          }
        />
      )}

      {status?.portfolioConnected && (
        <>
          <div className="app-inset grid gap-3 rounded-[22px] p-4">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 text-emerald-400" />
              <div>
                <p className="text-sm font-medium text-foreground">Portfolio data is connected</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Cerberus can use current holdings and connected risk inputs instead of generic “need data” prompts.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <p className="app-label">Quick Reviews</p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {quickActions.map((action) => (
              <button
                key={action.label}
                onClick={() => handleAction(action.prompt)}
                disabled={isLoading}
                className="app-inset rounded-[20px] px-3.5 py-3.5 text-left transition-all hover:border-primary/30 hover:bg-muted/20 disabled:opacity-50"
              >
                <span className="flex items-center gap-2 text-xs font-medium text-foreground">
                  <LineChart className="h-3.5 w-3.5 text-primary" />
                  {action.label}
                </span>
                <p className="mt-2 text-[11px] leading-5 text-muted-foreground">
                  {action.description}
                </p>
              </button>
            ))}
            </div>
          </div>
        </>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-4">
          <div className="flex space-x-1">
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" style={{ animationDelay: '0ms' }} />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" style={{ animationDelay: '150ms' }} />
            <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      )}
    </div>
  );
}
