'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Bot, Download, Sparkles } from 'lucide-react';
import { createBot, sendChatMessage } from '@/lib/cerberus-api';
import { parseStrategySpec, specToBuilderFields, type StrategySpec } from '@/lib/strategy-spec';
import { useStrategyBuilderStore } from '@/stores/strategy-builder-store';
import { useCerberusStore } from '@/stores/cerberus-store';
import { useUIContextStore } from '@/stores/ui-context-store';

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
  const selectedSymbol = pageContext.selectedSymbol?.toUpperCase();

  useEffect(() => {
    const seededPrompt = consumeStrategySeedPrompt();
    if (seededPrompt) {
      setStrategyPrompt(seededPrompt);
    }
  }, [consumeStrategySeedPrompt]);

  const runPrompt = async (prompt: string) => {
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

  const handleUseSelectedSymbol = () => {
    if (!selectedSymbol) return;
    setStrategyPrompt((current) => {
      if (current.toUpperCase().includes(selectedSymbol)) {
        return current;
      }

      const next = current.trim();
      return next
        ? `${next} Focus on ${selectedSymbol}.`
        : `Build a strategy for ${selectedSymbol}.`;
    });
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
        <div className="rounded-[22px] border border-border/60 bg-muted/20 p-4">
          <p className="app-label">What To Include</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            <div className="rounded-2xl border border-border/60 bg-background/55 px-3 py-3">
              <p className="text-xs font-medium text-foreground">Edge</p>
              <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                Describe the market behavior the bot should exploit.
              </p>
            </div>
            <div className="rounded-2xl border border-border/60 bg-background/55 px-3 py-3">
              <p className="text-xs font-medium text-foreground">Execution</p>
              <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                Name the timeframe, signals, and entry or exit structure.
              </p>
            </div>
            <div className="rounded-2xl border border-border/60 bg-background/55 px-3 py-3">
              <p className="text-xs font-medium text-foreground">Risk</p>
              <p className="mt-1 text-[11px] leading-5 text-muted-foreground">
                Add sizing rules, stops, and the conditions that should block trades.
              </p>
            </div>
          </div>

          {selectedSymbol && (
            <button
              type="button"
              onClick={handleUseSelectedSymbol}
              className="app-button-secondary mt-4 h-9 px-4 text-xs"
            >
              <ArrowRight className="h-3.5 w-3.5" />
              Use {selectedSymbol} context
            </button>
          )}
        </div>

        <textarea
          value={strategyPrompt}
          onChange={(e) => setStrategyPrompt(e.target.value)}
          placeholder="Describe your strategy idea..."
          rows={4}
          className="app-textarea min-h-[7rem] resize-none"
        />

        <button
          onClick={() => void runPrompt(strategyPrompt)}
          disabled={!strategyPrompt.trim() || isGenerating}
          className="app-button-primary w-full justify-center disabled:opacity-50"
        >
          {isGenerating ? 'Building strategy...' : 'Build Strategy'}
        </button>
      </div>

      {generatedStrategy && !importedBotId && (
        <div className="rounded-[22px] border border-primary/30 bg-primary/5 p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <span className="text-xs font-medium text-foreground">Strategy ready</span>
            <span className="truncate text-xs text-muted-foreground">{generatedStrategy.name}</span>
          </div>
          <button
            onClick={handleSendToBuilder}
            disabled={isSendingToBuilder}
            className="app-button-secondary w-full justify-center disabled:opacity-50"
          >
            <Bot className="h-3.5 w-3.5" />
            {isSendingToBuilder ? 'Opening builder...' : 'Send to builder'}
          </button>
          <button
            onClick={handleImportBot}
            disabled={isImporting}
            className="app-button-primary w-full justify-center disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            {isImporting ? 'Creating bot...' : 'Import strategy as bot'}
          </button>
        </div>
      )}

      {importedBotId && (
        <div className="rounded-[22px] border border-emerald-500/30 bg-emerald-500/5 p-3 text-center">
          <p className="text-xs font-medium text-emerald-400">Bot created</p>
          <p className="mt-0.5 text-xs text-muted-foreground">Opening Bots tab...</p>
        </div>
      )}
    </div>
  );
}
