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
  regime: string | null;
  confidence: number | null;
  volatility_20d: number | null;
  vol_percentile?: number | null;
  trend_strength: number | null;
  timestamp?: string | null;
  status?: "ready" | "no_data";
}

export interface EnsembleStatus {
  ensemble_active: boolean;
  model_count: number;
  weights: Record<string, number>;
  last_updated: string | null;
  status?: "ready" | "no_data";
  retraining_supported?: boolean;
}
