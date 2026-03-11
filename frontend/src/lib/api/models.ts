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
  ensemble_active: boolean;
  model_count: number;
  weights: Record<string, number>;
  last_updated: string | null;
  mode?: string;
}

export interface RetrainResponse {
  status: string;
  model: string;
  message: string;
  job_id: string;
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

export function triggerRetrain(modelName?: string): Promise<RetrainResponse> {
  const query = modelName
    ? `?model_name=${encodeURIComponent(modelName)}`
    : "";
  return apiFetch<RetrainResponse>(`/api/models/retrain${query}`, {
    method: "POST",
    maxRetries: 0,
  });
}
