export interface ModelDetail {
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

export interface RegimeData {
  regime: string;
  confidence: number;
  volatility_20d: number;
  vol_percentile: number;
  trend_strength: number;
}

export interface EnsembleStatus {
  ensemble_active: boolean;
  model_count: number;
  weights: Record<string, number>;
  last_updated: string | null;
}
