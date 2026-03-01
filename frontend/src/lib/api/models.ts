import { apiFetch } from "./client";
import type {
  ModelInfo,
  AllocationEntry,
  EquityCurvePoint,
} from "@/types/portfolio";

export interface MarketRegime {
  regime: string;
  confidence: number;
  volatility: number;
  trend: string;
  details?: Record<string, unknown>;
}

export interface EnsembleStatus {
  models: Record<string, unknown>[];
  weights: Record<string, number>;
  regime_weights: Record<string, Record<string, number>>;
}

export function getModels(): Promise<ModelInfo[]> {
  return apiFetch<ModelInfo[]>("/api/models/list");
}

export function getRegime(symbol: string = "SPY"): Promise<MarketRegime> {
  return apiFetch<MarketRegime>(`/api/models/regime?symbol=${symbol}`);
}

export function getAllocation(): Promise<AllocationEntry[]> {
  return apiFetch<AllocationEntry[]>("/api/models/allocation");
}

export function getEquityCurve(): Promise<{ results: EquityCurvePoint[] }> {
  return apiFetch<{ results: EquityCurvePoint[] }>("/api/dashboard/equity-curve");
}

export function getEnsembleStatus(): Promise<EnsembleStatus> {
  return apiFetch<EnsembleStatus>("/api/models/ensemble-status");
}

export function triggerRetrain(
  modelName: string
): Promise<{ model: string; retrained: boolean; metrics: Record<string, unknown> }> {
  return apiFetch("/api/models/retrain", {
    method: "POST",
    body: JSON.stringify({ model_name: modelName }),
  });
}
