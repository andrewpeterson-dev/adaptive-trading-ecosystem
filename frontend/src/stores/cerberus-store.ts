import { create } from 'zustand';
import type {
  ConversationThread,
  ConversationMessageItem,
  ConversationMode,
  TradeProposal,
  ToolCallEvent,
  AssistantMessage,
} from '@/types/cerberus';

type CerberusTab = 'chat' | 'strategy' | 'portfolio' | 'bots' | 'research';

interface CerberusState {
  // Panel state
  isOpen: boolean;
  activeTab: CerberusTab;

  // Conversation
  threads: ConversationThread[];
  activeThreadId: string | null;
  messages: ConversationMessageItem[];
  isStreaming: boolean;
  streamingContent: string;

  // Mode
  mode: ConversationMode;

  // Tool calls
  activeToolCalls: ToolCallEvent[];

  // Proposals
  pendingProposal: TradeProposal | null;

  // Actions
  openCerberus: () => void;
  closeCerberus: () => void;
  toggleCerberus: () => void;
  setActiveTab: (tab: CerberusTab) => void;
  setMode: (mode: ConversationMode) => void;

  // Thread management
  setThreads: (threads: ConversationThread[]) => void;
  setActiveThread: (threadId: string | null) => void;
  addMessage: (message: ConversationMessageItem) => void;
  setMessages: (messages: ConversationMessageItem[]) => void;
  clearMessages: () => void;

  // Streaming
  setStreaming: (streaming: boolean) => void;
  appendStreamContent: (content: string) => void;
  clearStreamContent: () => void;

  // Tool calls
  addToolCall: (toolCall: ToolCallEvent) => void;
  updateToolCall: (toolName: string, update: Partial<ToolCallEvent>) => void;
  clearToolCalls: () => void;

  // Proposals
  setPendingProposal: (proposal: TradeProposal | null) => void;
}

export const useCerberusStore = create<CerberusState>((set) => ({
  // Initial state
  isOpen: false,
  activeTab: 'chat',
  threads: [],
  activeThreadId: null,
  messages: [],
  isStreaming: false,
  streamingContent: '',
  mode: 'chat',
  activeToolCalls: [],
  pendingProposal: null,

  // Panel actions
  openCerberus: () => set({ isOpen: true }),
  closeCerberus: () => set({ isOpen: false }),
  toggleCerberus: () => set((state) => ({ isOpen: !state.isOpen })),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setMode: (mode) => set({ mode }),

  // Thread management
  setThreads: (threads) => set({ threads }),
  setActiveThread: (threadId) => set({ activeThreadId: threadId, messages: [], streamingContent: '' }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setMessages: (messages) => set({ messages }),
  clearMessages: () => set({ messages: [], streamingContent: '' }),

  // Streaming
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  appendStreamContent: (content) => set((state) => ({ streamingContent: state.streamingContent + content })),
  clearStreamContent: () => set({ streamingContent: '' }),

  // Tool calls
  addToolCall: (toolCall) => set((state) => ({ activeToolCalls: [...state.activeToolCalls, toolCall] })),
  updateToolCall: (toolName, update) => set((state) => ({
    activeToolCalls: state.activeToolCalls.map((tc) =>
      tc.toolName === toolName ? { ...tc, ...update } : tc
    ),
  })),
  clearToolCalls: () => set({ activeToolCalls: [] }),

  // Proposals
  setPendingProposal: (proposal) => set({ pendingProposal: proposal }),
}));
