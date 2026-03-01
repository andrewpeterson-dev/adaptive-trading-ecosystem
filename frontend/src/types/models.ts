export interface ModelDetail {
  name: string;
  type: string;
  version: string;
  is_trained: boolean;
  metrics: {
    sharpe_ratio: number;
    sortino_ratio: number;
    win_rate: number;
    profit_factor: number;
    max_drawdown: number;
    total_return: number;
    num_trades: number;
    avg_trade_pnl: number;
    last_updated: string;
  };
}

export interface RegimeData {
  regime: string;
  confidence: number;
  volatility_20d: number;
  vol_percentile: number;
  trend_strength: number;
}

export interface EnsembleStatus {
  models: Record<string, unknown>;
  weights: Record<string, number>;
  regime_weights: Record<string, Record<string, number>>;
}
