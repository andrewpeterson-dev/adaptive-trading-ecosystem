// UI Command System — Allowlisted actions and component IDs only. No arbitrary JS/CSS.

export type UICommandAction =
  | "open_panel"
  | "switch_tab"
  | "highlight_component"
  | "populate_strategy_builder"
  | "populate_order_ticket"
  | "navigate"
  | "show_chart"
  | "show_toast"
  | "focus_symbol"
  | "select_bot"
  | "open_confirmation_modal";

export type AllowlistedComponentId =
  | "portfolio_chart"
  | "positions_table"
  | "options_chain"
  | "risk_metrics"
  | "order_ticket"
  | "strategy_builder"
  | "bot_list"
  | "bot_performance_chart"
  | "trade_history_table"
  | "research_sources_panel";

export interface UICommand {
  action: UICommandAction;
  panel?: string;
  tab?: string;
  componentId?: AllowlistedComponentId;
  durationMs?: number;
  strategy?: Record<string, unknown>;
  orderTicket?: Record<string, unknown>;
  route?: string;
  chartSpec?: Record<string, unknown>;
  message?: string;
  toastType?: "info" | "success" | "warning" | "error";
  symbol?: string;
  botId?: string;
  proposalId?: string;
}

export interface UICommandEnvelope {
  commands: UICommand[];
}

export const ALLOWED_ACTIONS = new Set<UICommandAction>([
  "open_panel", "switch_tab", "highlight_component", "populate_strategy_builder",
  "populate_order_ticket", "navigate", "show_chart", "show_toast",
  "focus_symbol", "select_bot", "open_confirmation_modal",
]);

export const ALLOWED_COMPONENT_IDS = new Set<AllowlistedComponentId>([
  "portfolio_chart", "positions_table", "options_chain", "risk_metrics",
  "order_ticket", "strategy_builder", "bot_list", "bot_performance_chart",
  "trade_history_table", "research_sources_panel",
]);

export function validateUICommand(cmd: UICommand): boolean {
  if (!ALLOWED_ACTIONS.has(cmd.action)) return false;
  if (cmd.componentId && !ALLOWED_COMPONENT_IDS.has(cmd.componentId)) return false;
  if (cmd.action === "navigate" && cmd.route && !cmd.route.startsWith("/")) return false;
  return true;
}
