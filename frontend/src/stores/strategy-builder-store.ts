import { create } from "zustand";
import type { Action, StrategyCondition } from "@/types/strategy";

interface PendingStrategy {
  name: string;
  description: string;
  action: Action;
  stopLoss: number;
  takeProfit: number;
  positionSize: number;
  timeframe: string;
  conditions: StrategyCondition[];
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
