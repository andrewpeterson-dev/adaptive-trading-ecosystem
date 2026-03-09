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

/**
 * Derives ensemble status from the /api/models/list response.
 * The /api/models/ensemble-status route does not exist; this is a client-side fallback.
 */
export async function getEnsembleStatus(): Promise<EnsembleStatus> {
  const models = await apiFetch<ModelInfo[]>("/api/models/list");
  const list = Array.isArray(models) ? models : (models as any).models ?? [];
  const weights: Record<string, number> = {};
  for (const m of list) {
    if (m.name && m.is_active) {
      weights[m.name] = 1 / Math.max(list.filter((x: any) => x.is_active).length, 1);
    }
  }
  return { models: list, weights, regime_weights: {} };
}

// triggerRetrain is not available — route /api/models/retrain does not exist.
