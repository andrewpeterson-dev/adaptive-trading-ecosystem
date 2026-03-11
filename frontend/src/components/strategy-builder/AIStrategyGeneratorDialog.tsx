"use client";

import { useState } from "react";
import { BrainCircuit, Sparkles } from "lucide-react";

import { generateStrategyWithAI, type GeneratedStrategyResponse } from "@/lib/cerberus-api";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const EXAMPLE_PROMPTS = [
  "Build me a trading bot that buys stocks when the Fed signals rate cuts.",
  "Create a volatility breakout strategy for SPY options.",
  "Build a strategy based on earnings surprises.",
];

interface AIStrategyGeneratorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApplyDraft: (result: GeneratedStrategyResponse) => void;
}

export function AIStrategyGeneratorDialog({
  open,
  onOpenChange,
  onApplyDraft,
}: AIStrategyGeneratorDialogProps) {
  const [prompt, setPrompt] = useState(EXAMPLE_PROMPTS[0]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    setError(null);
    setIsGenerating(true);
    try {
      const result = await generateStrategyWithAI(prompt);
      onApplyDraft(result);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate strategy");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl overflow-hidden border border-border/70 bg-card p-0">
        <div className="bg-gradient-to-r from-sky-500/10 via-emerald-500/5 to-amber-400/10 p-6">
          <DialogHeader className="p-0">
            <div className="mb-3 inline-flex w-fit items-center gap-2 rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-400">
              <BrainCircuit className="h-3.5 w-3.5" />
              AI Strategy Generator
            </div>
            <DialogTitle className="text-2xl tracking-tight text-foreground">
              Generate an autonomous bot spec from plain language
            </DialogTitle>
            <DialogDescription className="max-w-2xl pt-2 text-sm leading-6 text-muted-foreground">
              Describe the idea in plain English. The AI will translate it into the same structured
              strategy schema used by the existing builder so you can inspect, edit, save, and deploy it.
            </DialogDescription>
          </DialogHeader>
        </div>

        <div className="space-y-5 p-6">
          <div className="space-y-2">
            <label className="app-label">Prompt</label>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={6}
              placeholder="Describe the strategy you want the AI to build..."
              className="app-input min-h-[10rem] w-full resize-none py-3 leading-6"
            />
          </div>

          <div className="space-y-2">
            <div className="app-label">Example prompts</div>
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_PROMPTS.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setPrompt(example)}
                  className="rounded-full border border-border/60 bg-muted/30 px-3 py-1.5 text-left text-xs text-muted-foreground transition-colors hover:border-primary/30 hover:bg-primary/5 hover:text-foreground"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="rounded-2xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-3 border-t border-border/60 pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-muted-foreground">
              Unsupported event-driven ideas are translated into the closest executable price, momentum,
              and participation proxies available in the builder schema.
            </p>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating || !prompt.trim()}
              className="app-button-primary min-w-[11rem] justify-center disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Sparkles className="h-3.5 w-3.5" />
              {isGenerating ? "Generating…" : "Generate Bot"}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
