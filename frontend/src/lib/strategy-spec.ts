/**
 * Parse and validate a strategy JSON spec from Cerberus chat responses.
 * Maps the spec to Strategy Builder fields.
 */

import type {
  Action,
  ConditionGroup,
  Operator,
  StrategyAiContext,
  StrategyCondition,
  StrategyType,
} from "@/types/strategy";

export interface AIThinking {
  marketRegimeCheck?: string;
  disruptionTriggers?: string[];
  adaptiveBehavior?: string;
}

export interface StrategySpec {
  name: string;
  description: string;
  action: "BUY" | "SELL";
  stopLossPct: number;
  takeProfitPct: number;
  positionPct: number;
  timeframe: string;
  entryConditions: SpecCondition[];
  exitConditions?: SpecCondition[];
  symbols?: string[];
  strategyType?: StrategyType;
  sourcePrompt?: string;
  overview?: string;
  featureSignals?: string[];
  assumptions?: string[];
  learningPlan?: Record<string, unknown>;
  aiThinking?: AIThinking;
}

export interface SpecCondition {
  logic: "AND" | "OR";
  indicator: string;
  params: Record<string, number>;
  operator?: string;
  value?: number;
  signal?: string;
  field?: string;
  compare_to?: string;
}

const VALID_ACTIONS: Action[] = ["BUY", "SELL"];
const VALID_TIMEFRAMES = ["1m", "5m", "15m", "1H", "4H", "1D", "1W"];
const VALID_OPERATORS: Operator[] = [">", "<", ">=", "<=", "==", "crosses_above", "crosses_below"];

function stringList(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean);
}

/**
 * Extract a JSON object from a text response.
 * Handles fenced code blocks, raw JSON, and edge cases like
 * strings containing braces inside JSON values.
 */
export function extractJson(text: string): string | null {
  // Try fenced code block first (```json ... ``` or ``` ... ```)
  const fenced = text.match(/```(?:json)?\s*\n?([\s\S]*?)```/);
  if (fenced) {
    const candidate = fenced[1].trim();
    // Validate it's actually parseable JSON
    try {
      JSON.parse(candidate);
      return candidate;
    } catch {
      // Fenced block wasn't valid JSON, fall through to raw extraction
    }
  }

  // Try raw JSON object — find the largest valid JSON object in the text
  const start = text.indexOf("{");
  if (start === -1) return null;

  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (ch === "\\") {
      escaped = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (ch === "{") depth++;
    else if (ch === "}") depth--;
    if (depth === 0) return text.slice(start, i + 1);
  }
  return null;
}

export type ParseResult =
  | { ok: true; spec: StrategySpec }
  | { ok: false; error: string };

/**
 * Parse and validate a strategy spec from raw text.
 */
export function parseStrategySpec(text: string): ParseResult {
  const jsonStr = extractJson(text);
  if (!jsonStr) return { ok: false, error: "No JSON found in response" };

  let raw: unknown;
  try {
    raw = JSON.parse(jsonStr);
  } catch {
    return { ok: false, error: "Invalid strategy JSON" };
  }

  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return { ok: false, error: "Invalid strategy JSON" };
  }

  const obj = raw as Record<string, unknown>;

  // Required string fields
  if (typeof obj.name !== "string" || !obj.name.trim()) {
    return { ok: false, error: "Missing or empty 'name'" };
  }
  if (typeof obj.action !== "string" || !VALID_ACTIONS.includes(obj.action as Action)) {
    return { ok: false, error: "Invalid 'action' (must be BUY or SELL)" };
  }
  if (typeof obj.timeframe !== "string" || !VALID_TIMEFRAMES.includes(obj.timeframe)) {
    return { ok: false, error: `Invalid 'timeframe' (must be one of: ${VALID_TIMEFRAMES.join(", ")})` };
  }

  // Required number fields
  for (const field of ["stopLossPct", "takeProfitPct", "positionPct"] as const) {
    if (typeof obj[field] !== "number" || obj[field] <= 0) {
      return { ok: false, error: `Invalid '${field}' (must be a positive number)` };
    }
  }

  // Entry conditions
  if (!Array.isArray(obj.entryConditions) || obj.entryConditions.length === 0) {
    return { ok: false, error: "Missing or empty 'entryConditions'" };
  }

  for (const cond of obj.entryConditions) {
    if (typeof cond !== "object" || !cond) {
      return { ok: false, error: "Invalid entry condition" };
    }
    if (typeof cond.indicator !== "string" || !cond.indicator.trim()) {
      return { ok: false, error: "Entry condition missing 'indicator'" };
    }
  }

  const spec: StrategySpec = {
    name: obj.name as string,
    description: (typeof obj.description === "string" ? obj.description : ""),
    action: obj.action as "BUY" | "SELL",
    stopLossPct: obj.stopLossPct as number,
    takeProfitPct: obj.takeProfitPct as number,
    positionPct: obj.positionPct as number,
    timeframe: obj.timeframe as string,
    entryConditions: obj.entryConditions as SpecCondition[],
    exitConditions: Array.isArray(obj.exitConditions) ? obj.exitConditions as SpecCondition[] : [],
  };

  const symbols = stringList(obj.symbols);
  if (symbols) {
    spec.symbols = symbols.map((symbol) => symbol.toUpperCase());
  }

  if (
    typeof obj.strategyType === "string" &&
    ["manual", "ai_generated", "custom"].includes(obj.strategyType)
  ) {
    spec.strategyType = obj.strategyType as StrategyType;
  }

  if (typeof obj.sourcePrompt === "string") {
    spec.sourcePrompt = obj.sourcePrompt;
  }

  if (typeof obj.overview === "string") {
    spec.overview = obj.overview;
  }

  const featureSignals = stringList(obj.featureSignals);
  if (featureSignals) {
    spec.featureSignals = featureSignals;
  }

  const assumptions = stringList(obj.assumptions);
  if (assumptions) {
    spec.assumptions = assumptions;
  }

  if (
    typeof obj.learningPlan === "object" &&
    obj.learningPlan !== null &&
    !Array.isArray(obj.learningPlan)
  ) {
    spec.learningPlan = obj.learningPlan as Record<string, unknown>;
  }

  if (
    typeof obj.aiThinking === "object" &&
    obj.aiThinking !== null &&
    !Array.isArray(obj.aiThinking)
  ) {
    spec.aiThinking = obj.aiThinking as AIThinking;
  }

  return { ok: true, spec };
}

/**
 * Convert a StrategySpec to Strategy Builder fields.
 */
export function specToBuilderFields(spec: StrategySpec): {
  name: string;
  description: string;
  action: Action;
  stopLoss: number;
  takeProfit: number;
  positionSize: number;
  timeframe: string;
  conditions: StrategyCondition[];
  conditionGroups: ConditionGroup[];
  symbols?: string[];
  strategyType?: StrategyType;
  sourcePrompt?: string;
  aiContext?: StrategyAiContext;
} {
  let condId = 0;
  const conditions: StrategyCondition[] = spec.entryConditions.map((c) => {
    condId++;
    const operator = (
      c.operator && VALID_OPERATORS.includes(c.operator as Operator)
        ? c.operator
        : "<"
    ) as Operator;
    const value = typeof c.value === "number" ? c.value : 0;

    return {
      id: `spec_${Date.now()}_${condId}`,
      indicator: c.indicator.toLowerCase(),
      operator,
      value,
      compare_to: c.compare_to,
      field: c.field,
      params: c.params || {},
      action: spec.action,
    };
  });

  const conditionGroups = conditions.reduce<ConditionGroup[]>((groups, condition, index) => {
    const raw = spec.entryConditions[index];
    if (raw.logic === "OR" || groups.length === 0) {
      groups.push({
        id: `group_${Date.now()}_${groups.length + 1}`,
        label: `Group ${String.fromCharCode(65 + groups.length)}`,
        conditions: [condition],
      });
      return groups;
    }

    groups[groups.length - 1].conditions.push(condition);
    return groups;
  }, []);

  return {
    name: spec.name,
    description: spec.description,
    action: spec.action,
    stopLoss: spec.stopLossPct,
    takeProfit: spec.takeProfitPct,
    positionSize: spec.positionPct,
    timeframe: spec.timeframe,
    conditions,
    conditionGroups,
    symbols: spec.symbols,
    strategyType: spec.strategyType,
    sourcePrompt: spec.sourcePrompt,
    aiContext: {
      overview: spec.overview,
      feature_signals: spec.featureSignals,
      assumptions: spec.assumptions,
      learning_plan: spec.learningPlan,
      exit_conditions: spec.exitConditions as Array<Record<string, unknown>> | undefined,
      ai_thinking: spec.aiThinking as Record<string, unknown> | undefined,
    },
  };
}
