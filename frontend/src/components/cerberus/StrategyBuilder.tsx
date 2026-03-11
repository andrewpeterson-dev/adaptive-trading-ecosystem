'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Bot, Download, Sparkles } from 'lucide-react';
import { createBot, sendChatMessage } from '@/lib/cerberus-api';
import { parseStrategySpec, specToBuilderFields, type StrategySpec } from '@/lib/strategy-spec';
import { useStrategyBuilderStore } from '@/stores/strategy-builder-store';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useUIContextStore } from '@/stores/ui-context-store';

const SAMPLE_PROMPTS = [
  'Covered call on NVDA with assignment risk controls.',
  'Momentum scalper for liquid tech names after opening range break.',
  'Mean reversion on SPY with RSI exhaustion and VWAP reclaim.',
  'Iron condor strategy around implied volatility crush after earnings.',
];

export function StrategyBuilder() {
  const router = useRouter();
  const [strategyPrompt, setStrategyPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedStrategy, setGeneratedStrategy] = useState<{ name: string; spec: StrategySpec } | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [isSendingToBuilder, setIsSendingToBuilder] = useState(false);
  const [importedBotId, setImportedBotId] = useState<string | null>(null);
  const {
    addMessage,
    activeThreadId,
    setActiveThread,
    setActiveTab,
    consumeStrategySeedPrompt,
  } = useCerberusStore();
  const { pageContext } = useUIContextStore();
  const setPendingSpec = useStrategyBuilderStore((state) => state.setPendingSpec);

  useEffect(() => {
    const seededPrompt = consumeStrategySeedPrompt();
    if (seededPrompt) {
      setStrategyPrompt(seededPrompt);
    }
  }, [consumeStrategySeedPrompt]);

  const runPrompt = async (
    prompt: string,
    options?: { sendToBuilderAfterParse?: boolean }
  ) => {
    if (!prompt.trim() || isGenerating) return;
    setIsGenerating(true);
    setGeneratedStrategy(null);
    setImportedBotId(null);

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
        mode: 'strategy',
        message: prompt,
        pageContext,
      });
      if (!activeThreadId) setActiveThread(response.threadId);
      if (response.message) {
        const markdown = response.message.markdown || '';
        addMessage({
          id: response.turnId,
          role: 'assistant',
          contentMd: markdown,
          structuredJson: response.message,
          modelName: null,
          citations: response.message.citations || [],
          toolCalls: [],
          createdAt: new Date().toISOString(),
        });
        const parsed = parseStrategySpec(markdown);
        if (parsed.ok) {
          const nextStrategy = {
            name: parsed.spec.name || 'AI Strategy',
            spec: parsed.spec,
          };
          setGeneratedStrategy(nextStrategy);
          if (options?.sendToBuilderAfterParse) {
            setPendingSpec(specToBuilderFields(nextStrategy.spec));
            router.push('/');
          }
        } else {
          setActiveTab('chat');
        }
      }
    } catch (error) {
      console.error('Strategy generation error:', error);
    } finally {
      setIsGenerating(false);
      setStrategyPrompt('');
    }
  };

  const handleSendToBuilder = async () => {
    if (!generatedStrategy || isSendingToBuilder) return;
    setIsSendingToBuilder(true);
    try {
      setPendingSpec(specToBuilderFields(generatedStrategy.spec));
      router.push('/');
    } finally {
      setIsSendingToBuilder(false);
    }
  };

  const handleImportBot = async () => {
    if (!generatedStrategy || isImporting) return;
    setIsImporting(true);
    try {
      const result = await createBot(generatedStrategy.name, generatedStrategy.spec);
      setImportedBotId(result.bot_id);
      setTimeout(() => setActiveTab('bots'), 800);
    } catch (error) {
      console.error('Bot import error:', error);
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="flex h-full flex-col space-y-4 overflow-y-auto p-4">
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-1">Cerberus Strategy Drafting</h3>
        <p className="text-xs text-muted-foreground">
          Cerberus turns plain-language ideas into a builder-ready spec, then you decide whether to send it into the main builder or import it as a bot.
        </p>
      </div>

      <div className="space-y-3">
        <div className="grid gap-2">
          {SAMPLE_PROMPTS.map((preset) => (
            <div
              key={preset}
              className="rounded-xl border border-border bg-background/60 p-3"
            >
              <p className="text-xs text-foreground">{preset}</p>
              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => setStrategyPrompt(preset)}
                  className="rounded-full border border-border px-3 py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
                >
                  Use prompt
                </button>
                <button
                  onClick={() => void runPrompt(preset, { sendToBuilderAfterParse: true })}
                  disabled={isGenerating}
                  className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1.5 text-[11px] font-medium text-primary transition-colors hover:bg-primary/15 disabled:opacity-50"
                >
                  <span className="inline-flex items-center gap-1.5">
                    <ArrowRight className="h-3 w-3" />
                    Send to builder
                  </span>
                </button>
              </div>
            </div>
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
          onClick={() => void runPrompt(strategyPrompt)}
          disabled={!strategyPrompt.trim() || isGenerating}
          className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          {isGenerating ? 'Building strategy...' : 'Build Strategy'}
        </button>
      </div>

      {generatedStrategy && !importedBotId && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-xs font-medium text-foreground">Strategy ready</span>
            <span className="truncate text-xs text-muted-foreground">{generatedStrategy.name}</span>
          </div>
          <button
            onClick={handleSendToBuilder}
            disabled={isSendingToBuilder}
            className="w-full flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted/40 disabled:opacity-50"
          >
            <Bot className="h-3.5 w-3.5" />
            {isSendingToBuilder ? 'Opening builder...' : 'Send to builder'}
          </button>
          <button
            onClick={handleImportBot}
            disabled={isImporting}
            className="w-full flex items-center justify-center gap-2 rounded-lg border border-primary bg-primary/10 px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            {isImporting ? 'Creating bot...' : 'Import strategy as bot'}
          </button>
        </div>
      )}

      {importedBotId && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-center">
          <p className="text-xs font-medium text-emerald-400">Bot created</p>
          <p className="mt-0.5 text-xs text-muted-foreground">Opening Bots tab...</p>
        </div>
      )}
    </div>
  );
}
