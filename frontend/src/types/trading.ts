export interface Account {
  equity: number;
  cash: number;
  buying_power: number;
  portfolio_value: number;
  currency?: string;
  status?: string;
  broker?: string;
  mode?: string;
  not_configured?: boolean;
  message?: string;
}

export interface Position {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  side: string;
}

export interface Order {
  id: string;
  symbol: string;
  direction: string;
  quantity: number;
  order_type: string;
  status: string;
  filled_price: number | null;
  limit_price: number | null;
  submitted_at: string;
  filled_at: string | null;
}

export interface RiskSummary {
  current_drawdown_pct: number;
  max_drawdown_limit_pct: number;
  current_exposure_pct: number;
  max_exposure_limit_pct: number;
  is_halted: boolean;
  halt_reason: string | null;
  trades_this_hour: number;
  max_trades_per_hour: number;
}

export type AssetMode = 'stocks' | 'options';

export type TradeSource = 'manual' | string;

export interface Quote {
  symbol: string;
  price: number;
  bid?: number;
  ask?: number;
  last?: number;
  change?: number;
  change_pct?: number;
  volume?: number;
}

export interface OptionContract {
  symbol: string;
  underlying: string;
  expiration: string;
  strike: number;
  type: 'call' | 'put';
  bid?: number;
  ask?: number;
  last?: number;
  volume?: number;
  open_interest?: number;
  implied_volatility?: number;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
}

export interface OptionPosition {
  contract: OptionContract;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
}
