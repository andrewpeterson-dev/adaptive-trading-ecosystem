import { apiFetch } from "./api/client";

// ── Types ───────────────────────────────────────────────────────────────────

export interface MarketEvent {
  id: string;
  event_type: string;
  impact: "LOW" | "MEDIUM" | "HIGH";
  symbols: string[];
  sectors: string[];
  headline: string;
  source: string;
  raw_data: Record<string, unknown>;
  detected_at: string | null;
  expires_at: string | null;
}

export interface RiskScore {
  score: number;
  level: "low" | "medium" | "high";
  components: Record<string, unknown>;
  active_events: number;
}

export interface TradeDecisionItem {
  id: string;
  symbol: string;
  strategy_signal: string;
  context_risk_level: string;
  ai_confidence: number;
  decision: string;
  reasoning: string;
  size_adjustment: number;
  delay_seconds: number;
  events_considered: string[];
  model_used: string;
  created_at: string | null;
}

export interface JournalEntry {
  id: string;
  trade_id: string;
  symbol: string;
  side: string;
  entry_price: number | null;
  exit_price: number | null;
  pnl: number | null;
  pnl_pct: number | null;
  vix_at_entry: number | null;
  ai_confidence_at_entry: number | null;
  ai_decision: string | null;
  ai_reasoning: string | null;
  regime_at_entry: string | null;
  outcome_tag: string | null;
  lesson_learned: string | null;
  created_at: string | null;
}

export interface RegimeStat {
  regime: string;
  total_trades: number;
  win_rate: number;
  avg_pnl: number;
  avg_confidence: number;
  sharpe: number;
  updated_at: string | null;
}

export interface Adaptation {
  id: string;
  adaptation_type: string;
  old_value: Record<string, unknown>;
  new_value: Record<string, unknown>;
  reasoning: string;
  confidence: number;
  auto_applied: boolean;
  created_at: string | null;
}

export interface UniverseCandidateItem {
  id: string;
  symbol: string;
  score: number;
  reason: string;
  scanned_at: string | null;
}

// ── API Calls ───────────────────────────────────────────────────────────────

export function getMarketEvents(params?: { event_type?: string; impact?: string; limit?: number }) {
  const qs = new URLSearchParams();
  if (params?.event_type) qs.set("event_type", params.event_type);
  if (params?.impact) qs.set("impact", params.impact);
  if (params?.limit) qs.set("limit", String(params.limit));
  const query = qs.toString();
  return apiFetch<MarketEvent[]>(`/api/reasoning/events${query ? `?${query}` : ""}`);
}

export function getRiskScore() {
  return apiFetch<RiskScore>("/api/reasoning/risk-score");
}

export function getBotDecisions(botId: string, limit = 20) {
  return apiFetch<TradeDecisionItem[]>(`/api/reasoning/bots/${botId}/decisions?limit=${limit}`);
}

export function getBotJournal(botId: string, limit = 20) {
  return apiFetch<JournalEntry[]>(`/api/reasoning/bots/${botId}/journal?limit=${limit}`);
}

export function getBotRegimeStats(botId: string) {
  return apiFetch<RegimeStat[]>(`/api/reasoning/bots/${botId}/regime-stats`);
}

export function getBotAdaptations(botId: string, limit = 20) {
  return apiFetch<Adaptation[]>(`/api/reasoning/bots/${botId}/adaptations?limit=${limit}`);
}

export function getBotUniverse(botId: string) {
  return apiFetch<UniverseCandidateItem[]>(`/api/reasoning/bots/${botId}/universe`);
}
