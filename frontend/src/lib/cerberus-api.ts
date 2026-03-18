import { apiFetch } from './api/client';
import type {
  ChatRequest, ChatResponse, ConversationThread,
  ConversationMessageItem, DocumentFile, TradeProposal,
} from '@/types/cerberus';
import type { StrategyAiContext, StrategyType } from '@/types/strategy';

export interface BotPerformanceSummary {
  trade_count: number;
  open_count?: number;
  closed_count?: number;
  avg_return_pct: number;
  total_net_pnl: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  total_gross_pnl: number;
  total_volume: number;
  win_rate: number;
  sharpe_ratio: number;
  max_drawdown: number;
  open_positions?: Array<{
    symbol: string;
    side: string;
    quantity: number;
    entryPrice: number;
    currentPrice: number;
    unrealizedPnl: number;
  }>;
  feature_signals: string[];
}

export interface BotLearningStatus {
  enabled: boolean;
  status: string;
  lastOptimizationAt: string | null;
  nextOptimizationAt?: string | null;
  method?: string | null;
  summary?: string | null;
  methods: string[];
  featureSignals: string[];
  metrics: BotPerformanceSummary;
  parameterAdjustments: Array<Record<string, unknown>>;
  cadenceMinutes?: number;
}

export interface BotLatestDecision {
  ai_confidence: number;
  context_risk_level: string;
  decision: string;
  created_at: string | null;
}

export interface BotSummary {
  id: string;
  name: string;
  status: string;
  createdAt: string | null;
  config: Record<string, unknown> | null;
  strategyId?: number | null;
  strategyType: StrategyType;
  overview: string;
  primarySymbol: string;
  performance: BotPerformanceSummary;
  learningStatus: BotLearningStatus;
  currentVersion: BotVersionSummary | null;
  latestDecision: BotLatestDecision | null;
  allocatedCapital: number | null;
}

export interface BotVersionSummary {
  id: string;
  versionNumber: number;
  diffSummary: string | null;
  createdBy: string | null;
  backtestRequired: boolean;
  backtestId: string | null;
  createdAt: string | null;
}

export interface BotTrade {
  id: string;
  symbol: string;
  side: string;
  entryAction?: string | null;
  exitAction?: string | null;
  quantity: number;
  entryPrice: number | null;
  exitPrice: number | null;
  grossPnl: number | null;
  netPnl: number | null;
  returnPct?: number | null;
  status: string;
  strategyTag?: string | null;
  createdAt: string | null;
  entryTs?: string | null;
  exitTs?: string | null;
  notes?: string | null;
  reasons?: string[];
  botExplanation?: string | null;
  probabilityScore?: number | null;
  riskAssessment?: string | null;
  indicatorSignals?: string[];
  stopLossPrice?: number | null;
  takeProfitPrice?: number | null;
}

export interface BotDetail extends BotSummary {
  sourcePrompt?: string | null;
  aiBrainConfig?: Record<string, unknown> | null;
  overrideLevel?: string;
  aggressiveness?: number;
  equityCurve: Array<{ date: string; value: number }>;
  trades: BotTrade[];
  versionHistory: BotVersionSummary[];
  optimizationHistory: Array<{
    id: string;
    method: string;
    status: string;
    summary: string | null;
    metrics: Record<string, unknown>;
    adjustments: Array<Record<string, unknown>>;
    sourceVersionId?: string | null;
    resultVersionId?: string | null;
    createdAt: string | null;
  }>;
  aiCapitalManagement?: boolean;
}

export interface GeneratedStrategyResponse {
  prompt: string;
  strategy_spec: Record<string, unknown>;
  builder_draft: {
    name: string;
    description: string;
    action: 'BUY' | 'SELL';
    stopLoss: number;
    takeProfit: number;
    positionSize: number;
    timeframe: string;
    conditions: Array<Record<string, unknown>>;
    conditionGroups?: Array<Record<string, unknown>>;
    symbols?: string[];
    strategyType?: StrategyType;
    sourcePrompt?: string;
    aiContext?: StrategyAiContext;
  };
  compiled_strategy: Record<string, unknown>;
  generation: {
    provider: string;
    model: string | null;
    validated: boolean;
  };
}

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  return apiFetch('/api/ai/chat', {
    method: 'POST',
    body: JSON.stringify(request),
    timeoutMs: 120_000,
  });
}

export async function listThreads(limit = 20): Promise<ConversationThread[]> {
  return apiFetch(`/api/ai/threads?limit=${limit}`);
}

export async function getThreadMessages(threadId: string, limit = 50): Promise<ConversationMessageItem[]> {
  return apiFetch(`/api/ai/threads/${threadId}/messages?limit=${limit}`);
}

export async function confirmTrade(proposalId: string): Promise<{ confirmationToken: string }> {
  return apiFetch('/api/ai/tools/confirm-trade', {
    method: 'POST',
    body: JSON.stringify({ proposalId }),
  });
}

export async function executeTrade(proposalId: string, confirmationToken: string): Promise<any> {
  return apiFetch('/api/ai/tools/execute-trade', {
    method: 'POST',
    body: JSON.stringify({ proposalId, confirmationToken }),
  });
}

export async function createBot(name: string, strategyJson: object): Promise<{ bot_id: string; name: string; status: string }> {
  return apiFetch('/api/ai/tools/create-bot', {
    method: 'POST',
    body: JSON.stringify({ name, strategy_json: strategyJson }),
  });
}

export async function generateStrategyWithAI(prompt: string): Promise<GeneratedStrategyResponse> {
  return apiFetch('/api/ai/tools/generate-strategy', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
    timeoutMs: 120_000,
  });
}

export async function deployBotFromStrategy(
  strategyId: number,
  name?: string,
  universeConfig?: Record<string, unknown>,
  overrideLevel?: string,
): Promise<{ bot_id: string; name: string; status: string }> {
  return apiFetch('/api/ai/tools/bots/from-strategy', {
    method: 'POST',
    body: JSON.stringify({
      strategy_id: strategyId,
      name,
      ...(universeConfig ? { universe_config: universeConfig } : {}),
      ...(overrideLevel ? { override_level: overrideLevel } : {}),
    }),
  });
}

export async function deployBot(
  botId: string,
  universeConfig?: Record<string, unknown>,
  overrideLevel?: string,
  allocatedCapital?: number | null,
  extendedHours?: boolean,
): Promise<{ bot_id: string; status: string }> {
  return apiFetch(`/api/ai/tools/bots/${botId}/deploy`, {
    method: 'POST',
    body: JSON.stringify({
      ...(universeConfig ? { universe_config: universeConfig } : {}),
      ...(overrideLevel ? { override_level: overrideLevel } : {}),
      ...(allocatedCapital != null ? { allocated_capital: allocatedCapital } : {}),
      ...(extendedHours != null ? { extended_hours: extendedHours } : {}),
    }),
  });
}

export async function updateBotCapital(
  botId: string,
  allocatedCapital: number | null,
): Promise<{ bot_id: string; allocated_capital: number | null }> {
  return apiFetch(`/api/ai/tools/bots/${botId}/capital`, {
    method: 'PATCH',
    body: JSON.stringify({ allocated_capital: allocatedCapital }),
  });
}

export async function updateAiCapitalManagement(
  botId: string,
  enabled: boolean,
): Promise<{ bot_id: string; ai_capital_management: boolean }> {
  return apiFetch(`/api/ai/tools/bots/${botId}/ai-capital`, {
    method: 'PATCH',
    body: JSON.stringify({ enabled }),
  });
}

export async function stopBot(botId: string): Promise<{ bot_id: string; status: string }> {
  return apiFetch(`/api/ai/tools/bots/${botId}/stop`, { method: 'POST' });
}

export async function listBots(): Promise<BotSummary[]> {
  return apiFetch('/api/ai/tools/bots');
}

export async function getBotDetail(botId: string): Promise<BotDetail> {
  return apiFetch(`/api/ai/tools/bots/${botId}`);
}

export async function listProposals(status?: string): Promise<TradeProposal[]> {
  const params = status ? `?status=${status}` : '';
  return apiFetch(`/api/ai/tools/proposals${params}`);
}

export async function uploadDocument(
  filename: string,
  mimeType: string
): Promise<{ documentId: string; uploadUrl: string; uploadHeaders: Record<string, string> }> {
  const response = await apiFetch<{
    documentId?: string;
    uploadUrl?: string;
    uploadHeaders?: Record<string, string>;
    document_id?: string;
    upload_url?: string;
    upload_headers?: Record<string, string>;
  }>('/api/documents/upload', {
    method: 'POST',
    body: JSON.stringify({ filename, mimeType }),
  });
  const documentId = response.documentId ?? response.document_id ?? '';
  const uploadUrl = response.uploadUrl ?? response.upload_url ?? '';
  const uploadHeaders = response.uploadHeaders ?? response.upload_headers ?? {};
  if (!documentId || !uploadUrl) {
    throw new Error('Upload service returned an incomplete response');
  }
  return {
    documentId,
    uploadUrl,
    uploadHeaders,
  };
}

export async function finalizeDocument(documentId: string): Promise<{ status: string }> {
  return apiFetch(`/api/documents/${documentId}/finalize`, { method: 'POST' });
}

export async function getDocumentStatus(documentId: string): Promise<{
  id: string;
  filename: string;
  status: string;
  indexedAt: string | null;
}> {
  return apiFetch(`/api/documents/${documentId}/status`);
}

export async function searchDocuments(query: string, documentIds?: string[], topK = 8): Promise<{ chunks: any[] }> {
  return apiFetch('/api/documents/search', {
    method: 'POST',
    body: JSON.stringify({ query, documentIds, topK }),
  });
}
