import { apiFetch } from "./client";
import type { Account, Position, Order, RiskSummary } from "@/types/trading";

export interface Trade {
  id: string;
  symbol: string;
  direction: string;
  quantity: number;
  price: number;
  status: string;
  timestamp: string;
}

export interface PaperPortfolio {
  equity: number;
  cash: number;
  buying_power: number;
  portfolio_value: number;
  total_pnl: number;
  total_pnl_pct: number;
}

export interface PaperPosition {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  side: string;
}

export interface PaperTrade {
  id: string;
  symbol: string;
  direction: string;
  quantity: number;
  price: number;
  timestamp: string;
  pnl?: number;
}

export function getAccount(): Promise<Account> {
  return apiFetch<Account>("/api/trading/account");
}

export function getPositions(): Promise<Position[]> {
  return apiFetch<Position[]>("/api/trading/positions");
}

export function getOrders(status: string = "open"): Promise<Order[]> {
  return apiFetch<Order[]>(`/api/trading/orders?status=${status}`);
}

export function getRiskSummary(): Promise<RiskSummary> {
  return apiFetch<RiskSummary>("/api/trading/risk-summary");
}

export function executeTrade(
  symbol: string,
  direction: string,
  quantity: number
): Promise<Trade> {
  return apiFetch<Trade>("/api/trading/execute", {
    method: "POST",
    body: JSON.stringify({ symbol, direction, quantity }),
  });
}

export function getPaperPortfolio(): Promise<PaperPortfolio> {
  return apiFetch<PaperPortfolio>("/api/paper/portfolio");
}

export function getPaperPositions(): Promise<PaperPosition[]> {
  return apiFetch<PaperPosition[]>("/api/paper/positions");
}

export function getPaperTrades(): Promise<PaperTrade[]> {
  return apiFetch<PaperTrade[]>("/api/paper/history");
}

export interface PaperTradeResult extends PaperTrade {
  executed: boolean;
  cost?: number;
  proceeds?: number;
  remaining_cash?: number;
}

export function executePaperTrade(
  symbol: string,
  direction: string,
  quantity: number
): Promise<PaperTradeResult> {
  return apiFetch<PaperTradeResult>("/api/paper/trade", {
    method: "POST",
    body: JSON.stringify({ symbol, side: direction, quantity, user_confirmed: true }),
  });
}
