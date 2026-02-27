import type { IndicatorMetadata, IndicatorId } from "@/types/indicators";

import rsiMeta from "@/lib/indicators/metadata/rsi.json";
import smaMeta from "@/lib/indicators/metadata/sma.json";
import emaMeta from "@/lib/indicators/metadata/ema.json";
import macdMeta from "@/lib/indicators/metadata/macd.json";
import bollingerMeta from "@/lib/indicators/metadata/bollinger_bands.json";
import atrMeta from "@/lib/indicators/metadata/atr.json";
import vwapMeta from "@/lib/indicators/metadata/vwap.json";
import stochasticMeta from "@/lib/indicators/metadata/stochastic.json";
import obvMeta from "@/lib/indicators/metadata/obv.json";

type ComputeFn = (params: Record<string, number>) => Promise<unknown>;

interface RegistryEntry {
  metadata: IndicatorMetadata;
  compute: ComputeFn;
}

async function fetchCompute(
  indicator: string,
  params: Record<string, number>
): Promise<unknown> {
  const res = await fetch("/api/strategies/compute-indicator", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ indicator, params }),
  });
  if (!res.ok) throw new Error(`Compute failed: ${res.statusText}`);
  return res.json();
}

const REGISTRY: Record<IndicatorId, RegistryEntry> = {
  rsi: {
    metadata: rsiMeta as IndicatorMetadata,
    compute: (p) => fetchCompute("rsi", p),
  },
  sma: {
    metadata: smaMeta as IndicatorMetadata,
    compute: (p) => fetchCompute("sma", p),
  },
  ema: {
    metadata: emaMeta as IndicatorMetadata,
    compute: (p) => fetchCompute("ema", p),
  },
  macd: {
    metadata: macdMeta as IndicatorMetadata,
    compute: (p) => fetchCompute("macd", p),
  },
  bollinger_bands: {
    metadata: bollingerMeta as IndicatorMetadata,
    compute: (p) => fetchCompute("bollinger_bands", p),
  },
  atr: {
    metadata: atrMeta as IndicatorMetadata,
    compute: (p) => fetchCompute("atr", p),
  },
  vwap: {
    metadata: vwapMeta as IndicatorMetadata,
    compute: (p) => fetchCompute("vwap", p),
  },
  stochastic: {
    metadata: stochasticMeta as IndicatorMetadata,
    compute: (p) => fetchCompute("stochastic", p),
  },
  obv: {
    metadata: obvMeta as IndicatorMetadata,
    compute: (p) => fetchCompute("obv", p),
  },
};

export function getIndicator(id: IndicatorId): RegistryEntry | undefined {
  return REGISTRY[id];
}

export function getIndicatorMetadata(id: IndicatorId): IndicatorMetadata | undefined {
  return REGISTRY[id]?.metadata;
}

export function getAllIndicators(): IndicatorMetadata[] {
  return Object.values(REGISTRY).map((e) => e.metadata);
}

export function getIndicatorsByCategory(
  category: string
): IndicatorMetadata[] {
  return getAllIndicators().filter((m) => m.category === category);
}

export function getCategories(): string[] {
  const cats = new Set(getAllIndicators().map((m) => m.category));
  return Array.from(cats).sort();
}

export function computeIndicator(
  id: IndicatorId,
  params: Record<string, number>
): Promise<unknown> {
  const entry = REGISTRY[id];
  if (!entry) throw new Error(`Unknown indicator: ${id}`);
  return entry.compute(params);
}

export default REGISTRY;
