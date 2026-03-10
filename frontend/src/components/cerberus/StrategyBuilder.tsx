'use client';

import { useState } from 'react';
import { useCerberusStore } from '@/stores/cerberus-store';
import { sendChatMessage, createBot } from '@/lib/cerberus-api';
import { useUIContextStore } from '@/stores/ui-context-store';
import { Bot, Download } from 'lucide-react';

function extractStrategyJson(markdown: string): { name: string; spec: object } | null {
  const codeBlockPattern = /```json\s*([\s\S]*?)\s*```/g;
  let match;
  while ((match = codeBlockPattern.exec(markdown)) !== null) {
    try {
      const parsed = JSON.parse(match[1]);
      if (parsed && parsed.action && Array.isArray(parsed.entryConditions)) {
        return { name: parsed.name || 'AI Strategy', spec: parsed };
      }
    } catch { /* skip invalid JSON */ }
  }
  return null;
}

export function StrategyBuilder() {
  const [strategyPrompt, setStrategyPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedStrategy, setGeneratedStrategy] = useState<{ name: string; spec: object } | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [importedBotId, setImportedBotId] = useState<string | null>(null);
  const { addMessage, activeThreadId, setActiveThread, setActiveTab } = useCerberusStore();
  const { pageContext } = useUIContextStore();

  const handleGenerate = async () => {
    if (!strategyPrompt.trim() || isGenerating) return;
    setIsGenerating(true);
    setGeneratedStrategy(null);
    setImportedBotId(null);

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
        const parsed = extractStrategyJson(markdown);
        if (parsed) {
          setGeneratedStrategy(parsed);
        } else {
          // No JSON extracted — switch to chat so user sees the full response
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
    <div className="flex flex-col h-full p-4 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-1">AI Strategy Builder</h3>
        <p className="text-xs text-muted-foreground">Describe a trading strategy and the AI will build, test, and deploy it.</p>
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
          {isGenerating ? 'Building strategy...' : 'Build Strategy'}
        </button>
      </div>

      {generatedStrategy && !importedBotId && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary" />
            <span className="text-xs font-medium text-foreground">Strategy ready</span>
            <span className="text-xs text-muted-foreground truncate">{generatedStrategy.name}</span>
          </div>
          <button
            onClick={handleImportBot}
            disabled={isImporting}
            className="w-full flex items-center justify-center gap-2 rounded-lg border border-primary bg-primary/10 px-4 py-2 text-sm font-medium text-primary hover:bg-primary/20 disabled:opacity-50 transition-colors"
          >
            <Download className="h-3.5 w-3.5" />
            {isImporting ? 'Creating bot...' : 'Import Strategy as Bot'}
          </button>
        </div>
      )}

      {importedBotId && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 text-center">
          <p className="text-xs font-medium text-emerald-400">Bot created</p>
          <p className="text-xs text-muted-foreground mt-0.5">Opening Bots tab...</p>
        </div>
      )}
    </div>
  );
}
