'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { listBots, deployBot, stopBot, type BotSummary } from '@/lib/cerberus-api';
import { Bot, Play, Square, RefreshCw, Rocket, Activity } from 'lucide-react';

const STATUS_COLOR: Record<string, string> = {
  running: 'text-emerald-400',
  draft:   'text-yellow-400',
  stopped: 'text-muted-foreground',
  paused:  'text-sky-400',
  error:   'text-red-400',
};

const STATUS_DOT: Record<string, string> = {
  running: 'bg-emerald-400 animate-pulse',
  draft:   'bg-yellow-400',
  stopped: 'bg-muted-foreground/40',
  paused:  'bg-sky-400',
  error:   'bg-red-400',
};

export function BotControlPanel() {
  const [bots, setBots] = useState<BotSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [actioningId, setActioningId] = useState<string | null>(null);

  const fetchBots = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listBots();
      setBots(data);
    } catch (error) {
      console.error('Failed to load bots:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchBots(); }, [fetchBots]);

  const handleDeploy = async (bot: BotSummary) => {
    setActioningId(bot.id);
    try {
      await deployBot(bot.id);
      setBots((prev) => prev.map((b) => b.id === bot.id ? { ...b, status: 'running' } : b));
    } catch (error) {
      console.error('Deploy error:', error);
    } finally {
      setActioningId(null);
    }
  };

  const handleStop = async (bot: BotSummary) => {
    setActioningId(bot.id);
    try {
      await stopBot(bot.id);
      setBots((prev) => prev.map((b) => b.id === bot.id ? { ...b, status: 'stopped' } : b));
    } catch (error) {
      console.error('Stop error:', error);
    } finally {
      setActioningId(null);
    }
  };

  const runningCount = bots.filter((b) => b.status === 'running').length;

  return (
    <div className="flex flex-col h-full p-4 space-y-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Your Bots</h3>
          {bots.length > 0 && (
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {runningCount} running · {bots.length} total
            </p>
          )}
        </div>
        <button
          onClick={fetchBots}
          disabled={isLoading}
          className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
          title="Refresh"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {bots.length === 0 && !isLoading && (
        <div className="text-center py-10 space-y-2">
          <Bot className="h-8 w-8 text-muted-foreground/30 mx-auto" />
          <p className="text-xs text-muted-foreground">No bots yet</p>
          <p className="text-[10px] text-muted-foreground/50">
            Go to Strategies → Deploy a strategy to create a bot
          </p>
        </div>
      )}

      {bots.length > 0 && (
        <div className="space-y-2">
          {bots.map((bot) => (
            <div
              key={bot.id}
              className="rounded-lg border border-border bg-card/50 p-3 space-y-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[bot.status] || 'bg-muted-foreground/40'}`} />
                  <span className="text-xs font-medium text-foreground truncate">{bot.name}</span>
                </div>
                <span className={`text-[10px] font-semibold uppercase tracking-wide ${STATUS_COLOR[bot.status] || 'text-muted-foreground'}`}>
                  {bot.status}
                </span>
              </div>

              {bot.config && (
                <p className="text-[10px] text-muted-foreground font-mono truncate">
                  {[
                    (bot.config.action as string) || '',
                    (bot.config.timeframe as string) || '',
                    Array.isArray(bot.config.symbols) && (bot.config.symbols as string[]).length > 0
                      ? (bot.config.symbols as string[]).slice(0, 3).join(', ')
                      : '',
                  ].filter(Boolean).join(' · ')}
                </p>
              )}

              <p className="text-[10px] leading-5 text-muted-foreground">
                {bot.overview || 'No natural-language overview yet.'}
              </p>

              <div className="grid grid-cols-3 gap-2 rounded-lg bg-muted/20 p-2 text-[10px]">
                <div>
                  <div className="text-muted-foreground/70">Win Rate</div>
                  <div className="font-mono text-foreground">{(bot.performance.win_rate * 100).toFixed(0)}%</div>
                </div>
                <div>
                  <div className="text-muted-foreground/70">Sharpe</div>
                  <div className="font-mono text-foreground">{bot.performance.sharpe_ratio.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-muted-foreground/70">Learning</div>
                  <div className="font-semibold text-emerald-400">{bot.learningStatus.status}</div>
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {(bot.status === 'draft' || bot.status === 'stopped') && (
                  <button
                    onClick={() => handleDeploy(bot)}
                    disabled={actioningId === bot.id}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-semibold text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/10 transition-colors disabled:opacity-50"
                  >
                    <Rocket className="h-2.5 w-2.5" />
                    {actioningId === bot.id ? 'Deploying…' : 'Deploy'}
                  </button>
                )}
                {bot.status === 'running' && (
                  <button
                    onClick={() => handleStop(bot)}
                    disabled={actioningId === bot.id}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-semibold text-red-400 border border-red-500/30 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                  >
                    <Square className="h-2.5 w-2.5" />
                    {actioningId === bot.id ? 'Stopping…' : 'Stop'}
                  </button>
                )}
                {bot.status === 'paused' && (
                  <button
                    onClick={() => handleDeploy(bot)}
                    disabled={actioningId === bot.id}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-semibold text-sky-400 border border-sky-500/30 hover:bg-sky-500/10 transition-colors disabled:opacity-50"
                  >
                    <Play className="h-2.5 w-2.5" />
                    Resume
                  </button>
                )}
                <Link
                  href={`/bots/${bot.id}`}
                  className="flex items-center gap-1 rounded-md border border-sky-500/30 px-2.5 py-1 text-[10px] font-semibold text-sky-400 transition-colors hover:bg-sky-500/10"
                >
                  <Activity className="h-2.5 w-2.5" />
                  View details
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
