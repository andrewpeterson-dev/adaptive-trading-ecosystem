import { apiFetch } from "./client";
import type {
  StrategyRecord,
  DiagnosticReport,
  StrategyExplanation,
} from "@/types/strategy";
import type { BacktestResult, BacktestRequest } from "@/types/backtest";

interface CreateStrategyData {
  name: string;
  description?: string;
  conditions: Array<{
    indicator: string;
    operator: string;
    value: number | string;
    compare_to?: string;
    params: Record<string, number>;
    action: string;
  }>;
  action?: string;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  position_size_pct?: number;
  timeframe?: string;
}

type UpdateStrategyData = Partial<CreateStrategyData>;

export async function listStrategies(): Promise<StrategyRecord[]> {
  const data = await apiFetch<{ strategies: StrategyRecord[] }>(
    "/api/strategies/list"
  );
  return data.strategies;
}

export function getStrategy(id: number): Promise<StrategyRecord> {
  return apiFetch<StrategyRecord>(`/api/strategies/${id}`);
}

export function createStrategy(data: CreateStrategyData): Promise<StrategyRecord> {
  return apiFetch<StrategyRecord>("/api/strategies/create", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateStrategy(
  id: number,
  data: UpdateStrategyData
): Promise<StrategyRecord> {
  return apiFetch<StrategyRecord>(`/api/strategies/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteStrategy(id: number): Promise<void> {
  return apiFetch<void>(`/api/strategies/${id}`, { method: "DELETE" });
}

export function diagnoseStrategy(
  conditions: Array<{
    indicator: string;
    operator: string;
    value: number | string;
    params: Record<string, number>;
    action: string;
  }>
): Promise<DiagnosticReport> {
  return apiFetch<DiagnosticReport>("/api/strategies/diagnose", {
    method: "POST",
    body: JSON.stringify({ conditions }),
  });
}

export function backtestStrategy(
  request: BacktestRequest
): Promise<BacktestResult> {
  return apiFetch<BacktestResult>("/api/strategies/backtest", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function explainStrategy(
  conditions: Array<{
    indicator: string;
    operator: string;
    value: number | string;
    params: Record<string, number>;
    action: string;
  }>
): Promise<StrategyExplanation> {
  return apiFetch<StrategyExplanation>("/api/explain", {
    method: "POST",
    body: JSON.stringify({ conditions }),
  });
}
