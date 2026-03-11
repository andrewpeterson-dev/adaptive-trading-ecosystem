"use client";

import { useMemo, useState } from "react";
import {
  Bot,
  BrainCircuit,
  Loader2,
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

import { ApiError } from "@/lib/api/client";
import {
  generateStrategyWithAI,
  sendChatMessage,
  type GeneratedStrategyResponse,
} from "@/lib/cerberus-api";
import {
  buildCerberusStrategyPrompt,
  buildGeneratedStrategyResult,
  DEFAULT_CERBERUS_STRATEGY_INPUT,
  type CerberusStrategyInput,
} from "@/lib/cerberus-strategy";
import { parseStrategySpec } from "@/lib/strategy-spec";
import { useCerberusStore } from "@/stores/cerberus-store";
import { useUIContextStore } from "@/stores/ui-context-store";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface AIStrategyGeneratorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApplyDraft: (result: GeneratedStrategyResponse) => void;
}

interface DraftPreview {
  draft: GeneratedStrategyResponse;
  fallbackReason: string | null;
}

const PROCESS_STEPS = [
  {
    icon: MessageSquareText,
    title: "Discovery",
    copy: "Cerberus reads the brief, infers the trading objective, and identifies missing execution details.",
  },
  {
    icon: Workflow,
    title: "Translation",
    copy: "Unsupported ideas get mapped into builder-compatible indicators, thresholds, and proxies.",
  },
  {
    icon: ShieldCheck,
    title: "Risk Design",
    copy: "Risk controls, sizing, exits, and assumptions are attached before the draft is handed over.",
  },
];

const BRIEF_TEMPLATES: Array<{
  label: string;
  input: Partial<CerberusStrategyInput>;
}> = [
  {
    label: "Breakout",
    input: {
      objective: "Build a breakout bot that waits for compression, expansion, and momentum confirmation before entering.",
      instrumentFocus: "stocks",
      timeframe: "1H",
      holdingStyle: "swing",
      directionBias: "two-sided",
    },
  },
  {
    label: "Trend Following",
    input: {
      objective: "Design a trend-following bot that adds only when strength persists and the tape stays orderly.",
      instrumentFocus: "stocks",
      timeframe: "1D",
      holdingStyle: "position",
      directionBias: "long-only",
    },
  },
  {
    label: "Mean Reversion",
    input: {
      objective: "Create a mean-reversion bot that buys oversold pullbacks inside established uptrends and exits into strength.",
      instrumentFocus: "stocks",
      timeframe: "4H",
      holdingStyle: "swing",
      directionBias: "long-only",
    },
  },
];

function ChoiceChips({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </div>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => onChange(option)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
              value === option
                ? "border-primary/40 bg-primary/10 text-foreground"
                : "border-border/60 bg-muted/25 text-muted-foreground hover:border-primary/20 hover:text-foreground"
            }`}
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}

export function AIStrategyGeneratorDialog({
  open,
  onOpenChange,
  onApplyDraft,
}: AIStrategyGeneratorDialogProps) {
  const [input, setInput] = useState<CerberusStrategyInput>(
    DEFAULT_CERBERUS_STRATEGY_INPUT
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<DraftPreview | null>(null);

  const { pageContext } = useUIContextStore();
  const {
    activeThreadId,
    addMessage,
    openCerberus,
    setActiveTab,
    setActiveThread,
  } = useCerberusStore();

  const aiContext = preview?.draft.builder_draft.aiContext;
  const assumptions = aiContext?.assumptions ?? [];
  const featureSignals = aiContext?.feature_signals ?? [];

  const generationSummary = useMemo(() => {
    if (!preview) return null;
    const draft = preview.draft.builder_draft;
    return {
      name: draft.name,
      overview: aiContext?.overview || draft.description,
      symbols: draft.symbols?.join(", ") || "Not specified",
      timeframe: draft.timeframe,
      action: draft.action,
    };
  }, [aiContext?.overview, preview]);

  const updateInput = <K extends keyof CerberusStrategyInput>(
    key: K,
    value: CerberusStrategyInput[K]
  ) => {
    setInput((current) => ({ ...current, [key]: value }));
    setPreview(null);
    setError(null);
  };

  const applyExample = (example: Partial<CerberusStrategyInput>) => {
    setInput((current) => ({ ...current, ...example }));
    setPreview(null);
    setError(null);
  };

  const handleContinueInCerberus = () => {
    openCerberus();
    setActiveTab("strategy");
  };

  const handleApplyDraft = () => {
    if (!preview) return;
    onApplyDraft(preview.draft);
    onOpenChange(false);
  };

  const tryFallbackGeneration = async (
    prompt: string,
    reason: string
  ): Promise<DraftPreview> => {
    const fallback = await generateStrategyWithAI(prompt);
    return {
      draft: fallback,
      fallbackReason: reason,
    };
  };

  const handleGenerate = async () => {
    setError(null);
    setPreview(null);
    setIsGenerating(true);

    const prompt = buildCerberusStrategyPrompt(input);

    addMessage({
      id: `user-${Date.now()}`,
      role: "user",
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
        mode: "strategy",
        message: prompt,
        pageContext,
      });

      if (!activeThreadId) {
        setActiveThread(response.threadId);
      }

      const markdown = response.message?.markdown || "";
      if (response.message) {
        addMessage({
          id: response.turnId,
          role: "assistant",
          contentMd: markdown,
          structuredJson: response.message,
          modelName: null,
          citations: response.message.citations || [],
          toolCalls: [],
          createdAt: new Date().toISOString(),
        });
      }

      const parsed = parseStrategySpec(markdown);
      if (!parsed.ok) {
        setPreview(
          await tryFallbackGeneration(
            prompt,
            `Cerberus returned a strategy review, but the draft was not machine-readable (${parsed.error}).`
          )
        );
        return;
      }

      setPreview({
        draft: buildGeneratedStrategyResult(parsed.spec, prompt),
        fallbackReason: null,
      });
    } catch (err) {
      try {
        const fallbackReason =
          err instanceof ApiError && err.status === 404
            ? "Cerberus strategy chat is not available on the current backend deployment."
            : "Cerberus strategy generation failed, so the direct strategy compiler was used instead.";
        setPreview(await tryFallbackGeneration(prompt, fallbackReason));
      } catch (fallbackError) {
        const fallbackMessage =
          fallbackError instanceof Error
            ? fallbackError.message
            : "Fallback generation failed";
        const primaryMessage =
          err instanceof Error ? err.message : "Cerberus generation failed";
        setError(`${primaryMessage} ${fallbackMessage}`.trim());
      }
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl border border-border/70 bg-card p-0">
        <div className="border-b border-border/60 bg-[linear-gradient(135deg,rgba(14,165,233,0.12),rgba(249,115,22,0.06),rgba(16,185,129,0.08))] px-6 py-6">
          <DialogHeader className="p-0">
            <div className="mb-3 inline-flex w-fit items-center gap-2 rounded-full border border-sky-400/20 bg-sky-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-400">
              <BrainCircuit className="h-3.5 w-3.5" />
              Cerberus Bot Designer
            </div>
            <DialogTitle className="text-2xl tracking-tight text-foreground">
              Build a trading bot with Cerberus
            </DialogTitle>
            <DialogDescription className="max-w-3xl pt-2 text-sm leading-6 text-muted-foreground">
              Cerberus should do more than one-shot prompt expansion. Give it a real brief, let it
              translate the idea into executable builder logic, review the assumptions, and only
              then apply the draft to the strategy builder.
            </DialogDescription>
          </DialogHeader>
        </div>

        <div className="grid gap-0 xl:grid-cols-[1.35fr,0.95fr]">
          <div className="space-y-5 p-6">
            <div className="space-y-2">
              <label className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                Primary Objective
              </label>
              <textarea
                value={input.objective}
                onChange={(event) => updateInput("objective", event.target.value)}
                rows={4}
                placeholder="Describe the edge, market behavior, and what the bot should exploit."
                className="app-input min-h-[8rem] w-full resize-none py-3 leading-6"
              />
            </div>

            <div className="space-y-2">
              <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                Starter Templates
              </div>
              <div className="flex flex-wrap gap-2">
                {BRIEF_TEMPLATES.map((example) => (
                  <button
                    key={example.label}
                    type="button"
                    onClick={() => applyExample(example.input)}
                    className="rounded-full border border-border/60 bg-muted/20 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/20 hover:bg-primary/5 hover:text-foreground"
                  >
                    {example.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                  Symbols or Universe
                </label>
                <input
                  value={input.symbols}
                  onChange={(event) => updateInput("symbols", event.target.value)}
                  placeholder="SPY, QQQ, NVDA"
                  className="app-input w-full"
                />
              </div>
              <ChoiceChips
                label="Instrument Focus"
                options={["stocks", "options", "mixed"]}
                value={input.instrumentFocus}
                onChange={(value) => updateInput("instrumentFocus", value)}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <ChoiceChips
                label="Preferred Timeframe"
                options={["15m", "1H", "4H", "1D", "1W"]}
                value={input.timeframe}
                onChange={(value) => updateInput("timeframe", value)}
              />
              <ChoiceChips
                label="Holding Style"
                options={["intraday", "swing", "position"]}
                value={input.holdingStyle}
                onChange={(value) => updateInput("holdingStyle", value)}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <ChoiceChips
                label="Direction Bias"
                options={["long-only", "short-only", "two-sided"]}
                value={input.directionBias}
                onChange={(value) => updateInput("directionBias", value)}
              />
              <ChoiceChips
                label="Risk Profile"
                options={["conservative", "balanced", "aggressive"]}
                value={input.riskProfile}
                onChange={(value) => updateInput("riskProfile", value)}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                  Required Signals
                </label>
                <textarea
                  value={input.requiredSignals}
                  onChange={(event) => updateInput("requiredSignals", event.target.value)}
                  rows={4}
                  placeholder="Momentum confirmation, volatility expansion, volume filter..."
                  className="app-input min-h-[7rem] w-full resize-none py-3 leading-6"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                  Constraints
                </label>
                <textarea
                  value={input.constraints}
                  onChange={(event) => updateInput("constraints", event.target.value)}
                  rows={4}
                  placeholder="Avoid low-volume names, prefer liquid ETFs, keep drawdowns tight..."
                  className="app-input min-h-[7rem] w-full resize-none py-3 leading-6"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                Extra Notes
              </label>
              <textarea
                value={input.notes}
                onChange={(event) => updateInput("notes", event.target.value)}
                rows={3}
                placeholder="Optional implementation details, market preferences, or hard limits."
                className="app-input min-h-[5.5rem] w-full resize-none py-3 leading-6"
              />
            </div>

            {error && (
              <div className="rounded-2xl border border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-400">
                {error}
              </div>
            )}

            <div className="flex flex-col gap-3 border-t border-border/60 pt-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="max-w-2xl text-xs leading-6 text-muted-foreground">
                The goal is not to impress you with generic AI copy. Cerberus should hand back a
                builder-compatible strategy, explain what had to be approximated, and preserve the
                reasoning so you can keep refining it.
              </p>
              <button
                type="button"
                onClick={handleGenerate}
                disabled={isGenerating || !input.objective.trim()}
                className="app-button-primary min-w-[13rem] justify-center disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isGenerating ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Sparkles className="h-3.5 w-3.5" />
                )}
                {isGenerating ? "Cerberus is designing..." : "Generate with Cerberus"}
              </button>
            </div>
          </div>

          <div className="border-t xl:border-t-0 xl:border-l border-border/60 bg-muted/10 p-6">
            <div className="rounded-3xl border border-border/60 bg-card/80 p-5">
              <div className="mb-4 flex items-center gap-2">
                <Bot className="h-4 w-4 text-primary" />
                <div>
                  <div className="text-sm font-semibold text-foreground">Cerberus Workflow</div>
                  <div className="text-xs text-muted-foreground">
                    Builder-first, bot-aware, and explicit about assumptions.
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                {PROCESS_STEPS.map((step) => {
                  const Icon = step.icon;
                  return (
                    <div
                      key={step.title}
                      className="rounded-2xl border border-border/50 bg-muted/15 p-3"
                    >
                      <div className="mb-1 flex items-center gap-2">
                        <Icon className="h-3.5 w-3.5 text-primary" />
                        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-foreground">
                          {step.title}
                        </div>
                      </div>
                      <p className="text-xs leading-5 text-muted-foreground">{step.copy}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="mt-5 rounded-3xl border border-border/60 bg-card/80 p-5">
              <div className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Draft Preview
              </div>

              {!preview && (
                <div className="space-y-3 text-sm text-muted-foreground">
                  <p>
                    Cerberus will return:
                  </p>
                  <ul className="space-y-2 text-xs leading-5">
                    <li>- A concrete strategy summary</li>
                    <li>- Executable indicator logic for the builder</li>
                    <li>- Feature signals and explicit assumptions</li>
                    <li>- A draft you can inspect before saving or deploying</li>
                  </ul>
                </div>
              )}

              {preview && generationSummary && (
                <div className="space-y-4">
                  {preview.fallbackReason && (
                    <div className="rounded-2xl border border-amber-400/20 bg-amber-400/5 px-3 py-2 text-xs leading-5 text-amber-500">
                      {preview.fallbackReason}
                    </div>
                  )}

                  <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4">
                    <div className="text-lg font-semibold tracking-tight text-foreground">
                      {generationSummary.name}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {generationSummary.overview || "Cerberus produced a builder-ready draft."}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-border/50 bg-muted/15 p-3">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        Action
                      </div>
                      <div className="mt-1 text-sm font-medium text-foreground">
                        {generationSummary.action}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-border/50 bg-muted/15 p-3">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        Timeframe
                      </div>
                      <div className="mt-1 text-sm font-medium text-foreground">
                        {generationSummary.timeframe}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-border/50 bg-muted/15 p-3">
                    <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Symbols
                    </div>
                    <div className="mt-1 text-sm font-medium text-foreground">
                      {generationSummary.symbols}
                    </div>
                  </div>

                  {featureSignals.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        Feature Signals
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {featureSignals.map((signal) => (
                          <span
                            key={signal}
                            className="rounded-full border border-border/60 bg-muted/15 px-2.5 py-1 text-xs text-foreground"
                          >
                            {signal}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {assumptions.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        Assumptions
                      </div>
                      <ul className="space-y-2 text-xs leading-5 text-muted-foreground">
                        {assumptions.map((assumption) => (
                          <li key={assumption}>- {assumption}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="flex flex-col gap-2 pt-2 sm:flex-row">
                    <button
                      type="button"
                      onClick={handleApplyDraft}
                      className="app-button-primary flex-1 justify-center"
                    >
                      Apply Draft to Builder
                    </button>
                    <button
                      type="button"
                      onClick={handleContinueInCerberus}
                      className="app-button-secondary flex-1 justify-center"
                    >
                      Continue in Cerberus
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
