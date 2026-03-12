import type { UICommand } from './ui-commands';

// Conversation types
export type ConversationMode = "chat" | "strategy" | "portfolio" | "bot_control" | "research";
export type MessageRole = "system" | "user" | "assistant" | "tool";

// Page context sent with every chat turn
export interface PageContext {
  currentPage: string;
  route: string;
  visibleComponents: string[];
  focusedComponent: string | null;
  selectedSymbol: string | null;
  selectedAccountId: string | null;
  selectedBotId: string | null;
  componentState: Record<string, unknown>;
}

// Chat API request/response
export interface ChatRequest {
  threadId?: string;
  mode: ConversationMode;
  message: string;
  pageContext: PageContext;
  attachments?: string[];
  selectedAccountId?: string;
  allowSlowExpertMode?: boolean;
}

export interface ChatResponse {
  threadId: string;
  turnId: string;
  streamChannel: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  message?: any;
}

// WebSocket stream events
export type StreamEventType =
  | "assistant.delta"
  | "assistant.message"
  | "tool.start"
  | "tool.result"
  | "chart.payload"
  | "ui.command"
  | "trade.proposal"
  | "warning"
  | "error"
  | "done";

export interface StreamEvent {
  type: StreamEventType;
  data: unknown;
}

// Assistant message (final normalized structure)
export interface AssistantMessage {
  turnId: string;
  markdown: string;
  citations: Citation[];
  structuredTradeSignals: TradeSignal[];
  charts: ChartSpec[];
  uiCommands: UICommand[];
  warnings: string[];
}

// Trade signals
export type StrategyType = "covered_call" | "long_call" | "iron_condor" | "stock" | "other";
export type TradeAction = "buy" | "sell" | "hold" | "review";

export interface TradeSignal {
  symbol: string;
  strategyType: StrategyType;
  action: TradeAction;
  confidence: number;
  thesis: string[];
  risks: string[];
  entry: { type: "market" | "limit"; price: number };
  exitPlan: { takeProfit: number; stopLoss: number; timeHorizon: string };
  requiresBacktest: boolean;
  requiresUserConfirmation: boolean;
}

// Trade proposals
export type ProposalStatus =
  | "draft" | "awaiting_confirmation" | "confirmed" | "expired"
  | "cancelled" | "executed" | "rejected";

export interface TradeProposal {
  id: string;
  symbol: string;
  assetType: "option" | "stock";
  side: "buy" | "sell";
  quantity: number;
  orderType: "market" | "limit" | "stop";
  limitPrice: number | null;
  timeInForce: "day" | "gtc";
  strategyType: StrategyType;
  thesis: string[];
  risks: string[];
  requiredChecks: string[];
  paperOrLive: "paper" | "live";
  status: ProposalStatus;
  riskSummary: Record<string, unknown>;
  explanationMd: string;
  expiresAt: string | null;
}

// Charts
export type ChartType = "line" | "candlestick" | "bar" | "equity_curve" | "allocation";

export interface ChartSpec {
  chartType: ChartType;
  title: string;
  series: ChartSeries[];
  xAxis: Record<string, unknown>;
  yAxis: Record<string, unknown>;
}

export interface ChartSeries {
  name: string;
  data: Array<{ x: string | number; y: number }>;
  color?: string;
}

// Citations
export interface Citation {
  source: "internal" | "external";
  title: string;
  url?: string;
  documentId?: string;
  chunkIds?: string[];
  pageNumber?: number;
  snippet?: string;
  date?: string;
}

// Tool calls
export type ToolCategory = "portfolio" | "trading" | "market" | "risk" | "research" | "analytics" | "ui";
export type ToolStatus = "pending" | "running" | "completed" | "failed";

export interface ToolCallEvent {
  toolName: string;
  category: ToolCategory;
  status: ToolStatus;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  latencyMs?: number;
  error?: string;
}

// Conversation list items
export interface ConversationThread {
  id: string;
  title: string | null;
  mode: ConversationMode;
  latestPage: string | null;
  latestSymbol: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConversationMessageItem {
  id: string;
  role: MessageRole;
  contentMd: string | null;
  structuredJson: AssistantMessage | null;
  modelName: string | null;
  citations: Citation[];
  toolCalls: ToolCallEvent[];
  createdAt: string;
}

// Documents
export type DocumentStatus = "uploaded" | "processing" | "indexed" | "failed";

export interface DocumentFile {
  id: string;
  originalFilename: string;
  mimeType: string | null;
  status: DocumentStatus;
  createdAt: string;
  indexedAt: string | null;
}

// Bots
export type BotStatus = "draft" | "running" | "active" | "paused" | "stopped" | "error" | "archived";

export interface Bot {
  id: string;
  name: string;
  status: BotStatus;
  currentVersionId: string | null;
  createdAt: string;
}

export interface BotVersion {
  id: string;
  botId: string;
  versionNumber: number;
  configJson: Record<string, unknown>;
  diffSummary: string | null;
  createdBy: "user" | "ai" | "system";
  backtestRequired: boolean;
  backtestId: string | null;
}
