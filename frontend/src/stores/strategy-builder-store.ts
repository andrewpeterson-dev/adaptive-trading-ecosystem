import { create } from "zustand";
import type {
  Action,
  ConditionGroup,
  StrategyAiContext,
  StrategyCondition,
  StrategyType,
} from "@/types/strategy";

interface PendingStrategy {
  name: string;
  description: string;
  action: Action;
  stopLoss: number;
  takeProfit: number;
  positionSize: number;
  timeframe: string;
  conditions: StrategyCondition[];
  conditionGroups?: ConditionGroup[];
  symbols?: string[];
  strategyType?: StrategyType;
  sourcePrompt?: string;
  aiContext?: StrategyAiContext;
}

interface StrategyBuilderState {
  pendingSpec: PendingStrategy | null;
  setPendingSpec: (spec: PendingStrategy | null) => void;
  consumePendingSpec: () => PendingStrategy | null;
}

export const useStrategyBuilderStore = create<StrategyBuilderState>((set, get) => ({
  pendingSpec: null,
  setPendingSpec: (spec) => set({ pendingSpec: spec }),
  consumePendingSpec: () => {
    const spec = get().pendingSpec;
    set({ pendingSpec: null });
    return spec;
  },
}));
