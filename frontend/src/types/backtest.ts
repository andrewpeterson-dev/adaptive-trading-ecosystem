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
  metrics: BacktestMetrics;
  equity_curve: { date: string; value: number }[];
  benchmark_equity_curve: { date: string; value: number }[];
  trades: BacktestTrade[];
  commission_pct: number;
  slippage_pct: number;
  synthetic_data?: boolean;
  data_warning?: string;
}

export interface BacktestRequest {
  strategy_id?: number;
  conditions?: Array<{
    indicator: string;
    operator: string;
    value: number | string;
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
