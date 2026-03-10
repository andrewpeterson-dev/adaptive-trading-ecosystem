'use client';

import { useState, useEffect, useCallback } from 'react';
import { sendChatMessage, listBots } from '@/lib/cerberus-api';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useUIContextStore } from '@/stores/ui-context-store';
import { Bot, Play, Square, RefreshCw } from 'lucide-react';

type BotEntry = {
  id: string;
  name: string;
  status: string;
  config: Record<string, unknown> | null;
  createdAt: string | null;
};

const STATUS_COLOR: Record<string, string> = {
  running:  'text-emerald-400',
  draft:    'text-yellow-400',
  stopped:  'text-muted-foreground',
  error:    'text-red-400',
};

export function BotControlPanel() {
  const [bots, setBots] = useState<BotEntry[]>([]);
  const [isLoadingBots, setIsLoadingBots] = useState(false);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const { addMessage, activeThreadId, setActiveThread } = useCerberusStore();
  const { pageContext } = useUIContextStore();

  const fetchBots = useCallback(async () => {
    setIsLoadingBots(true);
    try {
      const data = await listBots();
      setBots(data as BotEntry[]);
    } catch (error) {
      console.error('Failed to load bots:', error);
    } finally {
      setIsLoadingBots(false);
    }
  }, []);

  useEffect(() => {
    fetchBots();
  }, [fetchBots]);

  const handleAction = async (prompt: string) => {
    setIsChatLoading(true);
    addMessage({
      id: crypto.randomUUID(),
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
      // Refresh bot list after AI action
      await fetchBots();
    } catch (error) {
      console.error('Bot control error:', error);
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full p-4 space-y-4 overflow-y-auto">
      {/* Bot list */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Your Bots</h3>
        <button
          onClick={fetchBots}
          disabled={isLoadingBots}
          className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
          title="Refresh"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoadingBots ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {bots.length === 0 && !isLoadingBots && (
        <div className="text-center py-8 space-y-2">
          <Bot className="h-8 w-8 text-muted-foreground/30 mx-auto" />
          <p className="text-xs text-muted-foreground">No bots yet</p>
          <p className="text-xs text-muted-foreground/60">Build a strategy in the Strategy tab to create one</p>
        </div>
      )}

      {bots.length > 0 && (
        <div className="space-y-2">
          {bots.map((bot) => (
            <div
              key={bot.id}
              className="rounded-lg border border-border bg-card/50 p-3 space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <Bot className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <span className="text-xs font-medium text-foreground truncate">{bot.name}</span>
                </div>
                <span className={`text-[10px] font-medium uppercase tracking-wide ${STATUS_COLOR[bot.status] || 'text-muted-foreground'}`}>
                  {bot.status}
                </span>
              </div>
              {bot.config && (
                <p className="text-[10px] text-muted-foreground truncate">
                  {(bot.config as Record<string, unknown>).action as string || ''} · {(bot.config as Record<string, unknown>).timeframe as string || ''}
                </p>
              )}
              <div className="flex gap-1.5 pt-0.5">
                {bot.status === 'draft' && (
                  <button
                    onClick={() => handleAction(`Start bot ${bot.name} (id: ${bot.id})`)}
                    disabled={isChatLoading}
                    className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/10 transition-colors disabled:opacity-50"
                  >
                    <Play className="h-2.5 w-2.5" /> Start
                  </button>
                )}
                {bot.status === 'running' && (
                  <button
                    onClick={() => handleAction(`Stop bot ${bot.name} (id: ${bot.id})`)}
                    disabled={isChatLoading}
                    className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium text-red-400 border border-red-500/30 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                  >
                    <Square className="h-2.5 w-2.5" /> Stop
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Quick AI actions */}
      <div className="border-t border-border pt-3 space-y-2">
        <p className="text-xs text-muted-foreground font-medium">Ask AI</p>
        <div className="grid grid-cols-2 gap-2">
          {[
            { label: 'Bot Performance', prompt: 'Show performance metrics for all my active bots' },
            { label: 'Optimize Config', prompt: 'Suggest optimizations for my running bots based on recent performance' },
          ].map((a) => (
            <button
              key={a.label}
              onClick={() => handleAction(a.prompt)}
              disabled={isChatLoading}
              className="text-left px-3 py-2 rounded-lg border border-border hover:bg-muted hover:border-primary/30 transition-all text-xs font-medium text-foreground disabled:opacity-50"
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
