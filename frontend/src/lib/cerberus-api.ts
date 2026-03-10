import { apiFetch } from './api/client';
import type {
  ChatRequest, ChatResponse, ConversationThread,
  ConversationMessageItem, DocumentFile, TradeProposal,
} from '@/types/cerberus';

export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse & { message: any }> {
  return apiFetch('/api/ai/chat', {
    method: 'POST',
    body: JSON.stringify(request),
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

export async function deployBotFromStrategy(strategyId: number, name?: string): Promise<{ bot_id: string; name: string; status: string }> {
  return apiFetch('/api/ai/tools/bots/from-strategy', {
    method: 'POST',
    body: JSON.stringify({ strategy_id: strategyId, name }),
  });
}

export async function deployBot(botId: string): Promise<{ bot_id: string; status: string }> {
  return apiFetch(`/api/ai/tools/bots/${botId}/deploy`, { method: 'POST' });
}

export async function stopBot(botId: string): Promise<{ bot_id: string; status: string }> {
  return apiFetch(`/api/ai/tools/bots/${botId}/stop`, { method: 'POST' });
}

export async function listBots(): Promise<Array<{ id: string; name: string; status: string; config: object | null; createdAt: string | null }>> {
  return apiFetch('/api/ai/tools/bots');
}

export async function listProposals(status?: string): Promise<TradeProposal[]> {
  const params = status ? `?status=${status}` : '';
  return apiFetch(`/api/ai/tools/proposals${params}`);
}

export async function uploadDocument(filename: string, mimeType: string): Promise<{ documentId: string; uploadUrl: string }> {
  return apiFetch('/api/documents/upload', {
    method: 'POST',
    body: JSON.stringify({ filename, mimeType }),
  });
}

export async function finalizeDocument(documentId: string): Promise<{ status: string }> {
  return apiFetch(`/api/documents/${documentId}/finalize`, { method: 'POST' });
}

export async function searchDocuments(query: string, documentIds?: string[], topK = 8): Promise<{ chunks: any[] }> {
  return apiFetch('/api/documents/search', {
    method: 'POST',
    body: JSON.stringify({ query, documentIds, topK }),
  });
}
