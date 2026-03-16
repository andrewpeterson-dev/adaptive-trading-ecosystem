"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { LayoutItem, Layouts } from "@/components/dashboard/GridLayout";

// ---------------------------------------------------------------------------
// Default grid layout (12-column, rowHeight 40px)
// ---------------------------------------------------------------------------

const DEFAULT_LAYOUTS: Layouts = {
  lg: [
    { i: "strategy",        x: 0,  y: 0,  w: 3,  h: 8,  minW: 2,  minH: 4 },
    { i: "ai-reasoning",    x: 0,  y: 8,  w: 3,  h: 7,  minW: 2,  minH: 4 },
    { i: "ai-scanner",      x: 0,  y: 15, w: 3,  h: 6,  minW: 2,  minH: 3 },
    { i: "execution-chart", x: 3,  y: 0,  w: 6,  h: 10, minW: 4,  minH: 6 },
    { i: "risk-metrics",    x: 9,  y: 0,  w: 3,  h: 5,  minW: 2,  minH: 3 },
    { i: "sentiment",       x: 9,  y: 5,  w: 3,  h: 5,  minW: 2,  minH: 3 },
    { i: "equity-curve",    x: 0,  y: 21, w: 6,  h: 6,  minW: 3,  minH: 4 },
    { i: "open-positions",  x: 6,  y: 21, w: 6,  h: 6,  minW: 3,  minH: 4 },
    { i: "portfolio-risk",  x: 0,  y: 27, w: 6,  h: 6,  minW: 3,  minH: 4 },
    { i: "trade-log",       x: 6,  y: 27, w: 6,  h: 6,  minW: 3,  minH: 4 },
  ],
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

interface DashboardState {
  isLayoutLocked: boolean;
  layouts: Layouts;

  toggleLayoutLock: () => void;
  updateLayouts: (layouts: Layouts) => void;
}

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set) => ({
      isLayoutLocked: true,
      layouts: DEFAULT_LAYOUTS,

      toggleLayoutLock: () =>
        set((state) => ({ isLayoutLocked: !state.isLayoutLocked })),

      updateLayouts: (layouts) => set({ layouts }),
    }),
    {
      name: "dashboard-layout",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        isLayoutLocked: state.isLayoutLocked,
        layouts: state.layouts,
      }),
    },
  ),
);
