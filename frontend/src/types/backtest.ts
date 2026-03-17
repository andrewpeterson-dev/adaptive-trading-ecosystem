export interface BacktestMetrics {
  sharpe_ratio: number;
  sortino_ratio: number;
  win_rate: number;
  max_drawdown: number;
  total_return: number;
  num_trades: number;
  avg_trade_pnl: number;
  profit_factor: number;
}

export interface BacktestTrade {
  entry_date: string;
  exit_date: string;
  direction: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  bars_held: number;
}

export interface BacktestResult {
  symbol?: string;
  timeframe?: string;
  metrics: BacktestMetrics;
  equity_curve: { date: string; value: number }[];
  benchmark_equity_curve: { date: string; value: number }[];
  trades: BacktestTrade[];
  commission_pct: number;
  slippage_pct: number;
}

export interface BacktestRequest {
  strategy_id?: number;
  conditions?: Array<{
    indicator: string;
    operator: string;
    value: number | string;
    compare_to?: string;
    field?: string;
    params: Record<string, number>;
    action: string;
  }>;
  condition_groups?: Array<{
    id: string;
    conditions: BacktestRequest["conditions"];
  }>;
  symbol: string;
  lookback_days: number;
  initial_capital: number;
  commission_pct?: number;
  slippage_pct?: number;
}

// ── Walk-Forward Validation ──────────────────────────────────────────────

export interface WalkForwardSegment {
  start: string;
  end: string;
  metrics: {
    sharpe: number;
    total_return: number;
    max_drawdown: number;
    win_rate: number;
    num_trades: number;
  };
}

export interface WalkForwardResult {
  segments: WalkForwardSegment[];
  aggregate_metrics: {
    mean_sharpe: number;
    std_sharpe: number;
    mean_return: number;
    mean_max_drawdown: number;
    mean_win_rate: number;
    total_trades: number;
  };
  consistency_score: number;
  regime_adaptability_score: number;
  symbol: string;
  timeframe: string;
  n_segments: number;
  lookback_days: number;
}

// ── Ablation Study ───────────────────────────────────────────────────────

export interface AblationHistogramBin {
  bin_start: number;
  bin_end: number;
  count: number;
  contains_strategy: boolean;
}

export interface AblationResult {
  strategy_sharpe: number;
  random_mean_sharpe: number;
  random_std: number;
  percentile: number;
  p_value: number;
  is_significant: boolean;
  random_distribution_histogram: AblationHistogramBin[];
  n_random_trials: number;
  symbol: string;
  timeframe: string;
  lookback_days: number;
}

// ── Parameter Sweep ─────────────────────────────────────────────────────

export interface SweepDataPoint {
  params: Record<string, number>;
  value: number;
  metrics?: {
    total_return?: number;
    max_drawdown?: number;
    win_rate?: number;
    profit_factor?: number;
    equity_curve?: { date: string; value: number }[];
  };
}

export interface SweepResult {
  heatmap_data: SweepDataPoint[];
  heatmap?: SweepDataPoint[];
  best_params: Record<string, number>;
  best_value: number;
  param_axes: Record<string, number[]>;
  matrix?: number[][];
}
