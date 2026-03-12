export type Operator = ">" | "<" | ">=" | "<=" | "==" | "crosses_above" | "crosses_below";
export type LogicalJoiner = "AND" | "OR";

export type Action = "BUY" | "SELL";
export type StrategyType = "ai_generated" | "manual" | "custom";

export interface StrategyLearningPlan {
  enabled?: boolean;
  cadence_minutes?: number;
  methods?: string[];
  goals?: string[];
  status?: string;
  last_optimization_at?: string | null;
  last_summary?: string;
  parameter_adjustments?: Array<Record<string, unknown>>;
}

export interface StrategyAiThinking {
  marketRegimeCheck?: string;
  disruptionTriggers?: string[];
  adaptiveBehavior?: string;
}

export interface StrategyAiContext {
  overview?: string;
  feature_signals?: string[];
  assumptions?: string[];
  learning_plan?: StrategyLearningPlan;
  exit_conditions?: Array<Record<string, unknown>>;
  ai_thinking?: StrategyAiThinking | Record<string, unknown>;
  builder_preferences?: {
    order_type?: "market" | "limit" | "stop";
    backtest_period?: string;
    exit_logic?: string;
  };
  generation?: {
    generated_at?: string;
    provider?: string;
    model?: string | null;
    validated?: boolean;
  };
}

export interface StrategyCondition {
  id: string;
  indicator: string;
  operator: Operator;
  value: number | string;
  compare_to?: string;
  field?: string;
  joiner?: LogicalJoiner;
  params: Record<string, number>;
  action: Action;
}

export interface ConditionGroup {
  id: string;
  label?: string;
  joiner?: LogicalJoiner;
  conditions: StrategyCondition[];
}

export interface Strategy {
  id?: string;
  name: string;
  description: string;
  conditions?: StrategyCondition[];       // legacy — backward compat
  condition_groups: ConditionGroup[];     // primary representation
  action: Action;
  stop_loss_pct: number;
  take_profit_pct: number;
  position_size_pct: number;
  timeframe: string;
  // Universe
  symbols: string[];
  // Execution
  commission_pct: number;
  slippage_pct: number;
  // Exit
  trailing_stop_pct: number | null;
  exit_after_bars: number | null;
  // Risk
  cooldown_bars: number;
  max_trades_per_day: number;
  max_exposure_pct: number;
  max_loss_pct: number;
  strategy_type: StrategyType;
  source_prompt?: string | null;
  ai_context?: StrategyAiContext;
}

export interface Diagnostic {
  code: string;
  severity: "info" | "warning" | "critical";
  title: string;
  message: string;
  suggestion: string;
}

export interface DiagnosticReport {
  score: number;
  has_critical: boolean;
  total_issues: number;
  diagnostics: Diagnostic[];
}

export interface StrategyExplanation {
  summary: string;
  market_regime: string;
  strengths: string[];
  weaknesses: string[];
  risk_profile: string;
  overfitting_warning: boolean;
}

export interface StrategyRecord {
  id: number;
  name: string;
  description: string;
  conditions: Array<{
    indicator: string;
    operator: string;
    value: number | string;
    compare_to?: string;
    field?: string;
    params: Record<string, number>;
    action: string;
  }>;
  condition_groups: Array<{
    id: string;
    label?: string;
    conditions: StrategyRecord["conditions"];
  }>;
  action: string;
  stop_loss_pct: number;
  take_profit_pct: number;
  position_size_pct: number;
  timeframe: string;
  diagnostics: {
    score: number;
    total_issues: number;
    has_critical: boolean;
    diagnostics: Array<{
      code: string;
      severity: string;
      title: string;
      message: string;
      suggestion: string;
    }>;
  };
  created_at: string;
  updated_at: string;
  // Settings
  symbols: string[];
  commission_pct: number;
  slippage_pct: number;
  trailing_stop_pct: number | null;
  exit_after_bars: number | null;
  cooldown_bars: number;
  max_trades_per_day: number;
  max_exposure_pct: number;
  max_loss_pct: number;
  strategy_type: StrategyType;
  source_prompt?: string | null;
  ai_context?: StrategyAiContext;
}
