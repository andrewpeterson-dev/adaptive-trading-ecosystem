import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type {
  Action,
  ConditionGroup,
  DiagnosticReport,
  StrategyAiContext,
  StrategyExplanation,
  StrategyRecord,
  StrategyType,
} from "@/types/strategy";
import { specToBuilderFields } from "@/lib/strategy-spec";
import type { StrategySpec } from "@/lib/strategy-spec";

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

export interface BuilderState {
  // Identity
  name: string;
  description: string;
  action: Action;
  strategyType: StrategyType;
  timeframe: string;

  // Universe
  symbols: string[];

  // Entry / exit conditions
  conditionGroups: ConditionGroup[];
  exitConditionGroups: ConditionGroup[];

  // Risk
  stopLoss: number;
  takeProfit: number;
  positionSize: number;
  trailingStopEnabled: boolean;
  trailingStop: number;
  exitAfterBarsEnabled: boolean;
  exitAfterBars: number;
  exitLogic: string;
  cooldownBars: number;
  maxTradesPerDay: number;
  maxExposurePct: number;
  maxLossPct: number;

  // Execution
  orderType: string;
  backtestPeriod: string;
  commissionPct: number;
  slippagePct: number;

  // AI provenance
  sourcePrompt: string;
  aiContext: StrategyAiContext | null;
  aiBaselineFingerprint: string | null;

  // Transient (excluded from persistence)
  diagnostics: DiagnosticReport | null;
  explanation: StrategyExplanation | null;
  indicatorPreviews: Record<string, unknown>;
}

interface BuilderActions {
  setField: <K extends keyof BuilderState>(field: K, value: BuilderState[K]) => void;
  loadFromSpec: (spec: StrategySpec) => void;
  loadFromStrategy: (record: StrategyRecord) => void;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_STATE: BuilderState = {
  name: "",
  description: "",
  action: "BUY",
  strategyType: "manual",
  timeframe: "1D",

  symbols: [],

  conditionGroups: [{ id: "A", conditions: [], joiner: "AND" }],
  exitConditionGroups: [],

  stopLoss: 2,
  takeProfit: 5,
  positionSize: 5,
  trailingStopEnabled: false,
  trailingStop: 1,
  exitAfterBarsEnabled: false,
  exitAfterBars: 10,
  exitLogic: "stop_target",
  cooldownBars: 0,
  maxTradesPerDay: 10,
  maxExposurePct: 100,
  maxLossPct: 10,

  orderType: "market",
  backtestPeriod: "6M",
  commissionPct: 0.1,
  slippagePct: 0.05,

  sourcePrompt: "",
  aiContext: null,
  aiBaselineFingerprint: null,

  diagnostics: null,
  explanation: null,
  indicatorPreviews: {},
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useBuilderStore = create<BuilderState & BuilderActions>()(
  persist(
    (set) => ({
      ...DEFAULT_STATE,

      setField: (field, value) => set({ [field]: value } as Partial<BuilderState>),

      loadFromSpec: (spec) => {
        const fields = specToBuilderFields(spec);
        set({
          ...DEFAULT_STATE,
          name: fields.name,
          description: fields.description,
          action: fields.action,
          stopLoss: fields.stopLoss,
          takeProfit: fields.takeProfit,
          positionSize: fields.positionSize,
          timeframe: fields.timeframe,
          conditionGroups: fields.conditionGroups,
          symbols: fields.symbols ?? [],
          strategyType: fields.strategyType ?? "ai_generated",
          sourcePrompt: fields.sourcePrompt ?? "",
          aiContext: fields.aiContext ?? null,
        });
      },

      loadFromStrategy: (record) => {
        set({
          ...DEFAULT_STATE,
          name: record.name,
          description: record.description,
          action: record.action as Action,
          conditionGroups: record.condition_groups as ConditionGroup[],
          stopLoss: record.stop_loss_pct,
          takeProfit: record.take_profit_pct,
          positionSize: record.position_size_pct,
          timeframe: record.timeframe,
          symbols: record.symbols,
          commissionPct: record.commission_pct,
          slippagePct: record.slippage_pct,
          trailingStopEnabled: record.trailing_stop_pct != null && record.trailing_stop_pct > 0,
          trailingStop: record.trailing_stop_pct ?? 1,
          exitAfterBarsEnabled: record.exit_after_bars != null && record.exit_after_bars > 0,
          exitAfterBars: record.exit_after_bars ?? 10,
          cooldownBars: record.cooldown_bars,
          maxTradesPerDay: record.max_trades_per_day,
          maxExposurePct: record.max_exposure_pct,
          maxLossPct: record.max_loss_pct,
          strategyType: record.strategy_type,
          sourcePrompt: record.source_prompt ?? "",
          aiContext: record.ai_context ?? null,
        });
      },

      reset: () => {
        if (typeof window !== "undefined") {
          localStorage.removeItem("strategy_builder_draft");
        }
        set({ ...DEFAULT_STATE });
      },
    }),
    {
      name: "strategy_builder_draft",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => {
        // Exclude transient fields from persistence
        const { diagnostics, explanation, indicatorPreviews, ...persisted } = state;
        return persisted;
      },
    },
  ),
);
