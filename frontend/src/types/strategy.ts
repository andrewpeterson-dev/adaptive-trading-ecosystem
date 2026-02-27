export type Operator = ">" | "<" | ">=" | "<=" | "==" | "crosses_above" | "crosses_below";

export type Action = "BUY" | "SELL";

export interface StrategyCondition {
  id: string;
  indicator: string;
  operator: Operator;
  value: number | string;
  compare_to?: string;
  params: Record<string, number>;
  action: Action;
}

export interface Strategy {
  id?: string;
  name: string;
  description: string;
  conditions: StrategyCondition[];
  action: Action;
  stop_loss_pct: number;
  take_profit_pct: number;
  position_size_pct: number;
  timeframe: string;
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
