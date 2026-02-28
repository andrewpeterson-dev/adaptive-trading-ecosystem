export interface ModelInfo {
  name: string;
  model_type: string;
  is_active: boolean;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  win_rate: number | null;
  max_drawdown: number | null;
  total_return: number | null;
  num_trades: number;
}

export interface AllocationEntry {
  model_name: string;
  weight: number;
  allocated_capital: number;
}

export interface EquityCurvePoint {
  date: string;
  value: number;
}
