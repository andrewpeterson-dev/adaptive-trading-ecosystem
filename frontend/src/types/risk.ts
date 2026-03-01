export interface RiskEvent {
  timestamp: string;
  event_type: string;
  description: string;
}

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface RiskGaugeConfig {
  label: string;
  current: number;
  limit: number;
  unit: string;
}

export interface RiskSummaryExtended {
  is_halted: boolean;
  halt_reason: string | null;
  current_drawdown_pct: number;
  max_drawdown_limit: number;
  peak_equity: number;
  open_positions: number;
  trades_last_hour: number;
  recent_risk_events: number;
}
