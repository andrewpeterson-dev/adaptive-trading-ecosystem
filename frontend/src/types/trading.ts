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
  asset_type?: 'stock' | 'option';
  source?: TradeSource;
  bot_name?: string | null;
  stop_loss?: number | null;
  take_profit?: number | null;
  // Option-specific fields
  contract_symbol?: string;
  underlying?: string;
  expiration?: string;
  strike?: number;
  option_type?: 'call' | 'put';
  avg_premium?: number;
  current_mark?: number;
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
  stop_price: number | null;
  submitted_at: string;
  filled_at: string | null;
  asset_type?: 'stock' | 'option';
  source?: TradeSource;
  bot_name?: string | null;
  estimated_cost?: number | null;
}

export interface NewsArticle {
  title: string;
  url: string;
  source?: string;
  published_at?: string;
  summary?: string;
  symbols?: string[];
}

export interface SymbolSnapshot {
  symbol: string;
  name?: string;
  exchange?: string;
  price: number;
  bid?: number;
  ask?: number;
  last?: number;
  change?: number;
  change_pct?: number;
  volume?: number;
  market_cap?: number | null;
  pe_ratio?: number | null;
  fifty_two_week_low?: number | null;
  fifty_two_week_high?: number | null;
  dividend_yield?: number | null;
  avg_volume?: number | null;
  market_state?: string | null;
  currency?: string | null;
  source?: string | null;
  sector?: string | null;
  industry?: string | null;
  description?: string | null;
}

export interface TradingConnectionServiceStatus {
  status: 'connected' | 'warning' | 'disconnected';
  message: string;
  source?: string | null;
}

export interface TradingConnectionStatus {
  mode: string;
  broker?: string | null;
  market_data: TradingConnectionServiceStatus;
  order_routing: TradingConnectionServiceStatus;
}

export interface Trade {
  id: string;
  symbol: string;
  asset_type: 'stock' | 'option';
  direction: string;
  quantity: number;
  order_type: string;
  status: string;
  filled_price: number | null;
  entry_price: number | null;
  limit_price: number | null;
  stop_price: number | null;
  submitted_at: string;
  filled_at: string | null;
  pnl: number | null;
  total_value: number | null;
  source: TradeSource;
  bot_name: string | null;
  bot_explanation: string | null;
  // Option-specific
  contract_symbol?: string;
  underlying?: string;
  expiration?: string;
  strike?: number;
  option_type?: 'call' | 'put';
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

export type TradeFilter = 'all' | 'stocks' | 'options' | 'buys' | 'sells' | 'manual' | 'bot';

export interface Quote {
  symbol: string;
  name?: string;
  exchange?: string;
  price: number;
  bid?: number;
  ask?: number;
  last?: number;
  change?: number;
  change_pct?: number;
  volume?: number;
  high?: number;
  low?: number;
  open?: number;
  prev_close?: number;
  market_cap?: number | null;
  pe_ratio?: number | null;
  week52_high?: number | null;
  week52_low?: number | null;
  dividend_yield?: number | null;
  average_volume?: number | null;
  sector?: string | null;
  industry?: string | null;
  company_summary?: string | null;
  currency?: string | null;
  market_status?: string | null;
  source?: string | null;
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

export interface SymbolSearchResult {
  symbol: string;
  name: string;
  exchange?: string;
  type: 'stock' | 'etf' | 'crypto';
  price?: number;
  change?: number;
  change_pct?: number;
  volume?: number;
}
