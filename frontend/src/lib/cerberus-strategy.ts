import type { GeneratedStrategyResponse } from "@/lib/cerberus-api";
import { specToBuilderFields, type StrategySpec } from "@/lib/strategy-spec";

export interface CerberusStrategyInput {
  objective: string;
  instrumentFocus: string;
  symbols: string;
  timeframe: string;
  holdingStyle: string;
  directionBias: string;
  riskProfile: string;
  requiredSignals: string;
  constraints: string;
  notes: string;
}

export const DEFAULT_CERBERUS_STRATEGY_INPUT: CerberusStrategyInput = {
  objective: "Create a volatility breakout strategy for SPY options exposure.",
  instrumentFocus: "options",
  symbols: "SPY",
  timeframe: "1H",
  holdingStyle: "swing",
  directionBias: "two-sided",
  riskProfile: "balanced",
  requiredSignals: "Use volatility expansion, momentum confirmation, and clear exits.",
  constraints:
    "Keep it executable inside the existing builder. If options-specific logic is not directly supported, translate it into the best underlying-price proxy and explain the tradeoff.",
  notes: "",
};

export function buildCerberusStrategyPrompt(input: CerberusStrategyInput): string {
  return [
    "Design an autonomous trading bot draft for the existing Strategy Builder.",
    "Use an internal Cerberus design process:",
    "- translate the objective into builder-compatible logic",
    "- choose the strongest executable indicators and thresholds",
    "- define risk controls and position sizing",
    "- explain every major proxy or assumption clearly",
    "",
    "Return a machine-readable strategy JSON that matches the strategy-mode schema.",
    "Populate these optional fields as well: symbols, strategyType, sourcePrompt, overview, featureSignals, assumptions, learningPlan.",
    "Set strategyType to 'ai_generated'.",
    "Set sourcePrompt to the full brief below.",
    "",
    "User brief:",
    `- Primary objective: ${input.objective.trim() || "Not provided"}`,
    `- Instrument focus: ${input.instrumentFocus}`,
    `- Symbols or universe: ${input.symbols.trim() || "Not provided"}`,
    `- Preferred timeframe: ${input.timeframe}`,
    `- Holding style: ${input.holdingStyle}`,
    `- Direction bias: ${input.directionBias}`,
    `- Risk profile: ${input.riskProfile}`,
    `- Required signals or behaviors: ${input.requiredSignals.trim() || "Not provided"}`,
    `- Constraints and exclusions: ${input.constraints.trim() || "Not provided"}`,
    `- Extra notes: ${input.notes.trim() || "None"}`,
    "",
    "Important requirements:",
    "- The strategy must be executable in the current builder with supported indicators only.",
    "- If the request references options, macro events, or other unsupported primitives, map them to the closest executable price, volatility, momentum, or participation proxy.",
    "- Mention those approximations in overview and assumptions.",
    "- Keep the logic specific enough that the builder draft is immediately usable.",
  ].join("\n");
}

export function buildGeneratedStrategyResult(
  spec: StrategySpec,
  prompt: string,
  provider = "cerberus"
): GeneratedStrategyResponse {
  const normalizedSpec: StrategySpec = {
    ...spec,
    strategyType: spec.strategyType ?? "ai_generated",
    sourcePrompt: spec.sourcePrompt ?? prompt,
  };
  const builderDraft = specToBuilderFields(normalizedSpec);

  if (!builderDraft.sourcePrompt) {
    builderDraft.sourcePrompt = prompt;
  }
  if (builderDraft.aiContext) {
    builderDraft.aiContext.generation = {
      ...(builderDraft.aiContext.generation || {}),
      provider,
      model: null,
      validated: true,
    };
  }

  const responseBuilderDraft =
    builderDraft as unknown as GeneratedStrategyResponse["builder_draft"];

  return {
    prompt,
    strategy_spec: normalizedSpec as unknown as Record<string, unknown>,
    builder_draft: responseBuilderDraft,
    compiled_strategy: {
      name: builderDraft.name,
      action: builderDraft.action,
      timeframe: builderDraft.timeframe,
      condition_groups: builderDraft.conditionGroups,
      symbols: builderDraft.symbols,
      strategy_type: builderDraft.strategyType,
      source_prompt: builderDraft.sourcePrompt,
      ai_context: builderDraft.aiContext,
    },
    generation: {
      provider,
      model: null,
      validated: true,
    },
  };
}
