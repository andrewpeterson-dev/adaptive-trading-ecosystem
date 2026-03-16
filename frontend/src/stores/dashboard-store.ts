"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { LayoutItem, Layouts } from "@/components/dashboard/GridLayout";

// ---------------------------------------------------------------------------
// Default grid layout (12-column, rowHeight 40px)
// ---------------------------------------------------------------------------

/** Bumped LAYOUT_VERSION to bust stale localStorage when defaults change. */
const LAYOUT_VERSION = 2;

const DEFAULT_LAYOUTS: Layouts = {
  lg: [
    { i: "strategy",        x: 0, y: 0,  w: 3, h: 8,  minW: 2, minH: 5 },
    { i: "ai-reasoning",    x: 0, y: 8,  w: 3, h: 8,  minW: 2, minH: 5 },
    { i: "ai-scanner",      x: 0, y: 16, w: 3, h: 7,  minW: 2, minH: 4 },
    { i: "execution-chart", x: 3, y: 0,  w: 6, h: 12, minW: 4, minH: 8 },
    { i: "risk-metrics",    x: 9, y: 0,  w: 3, h: 6,  minW: 2, minH: 4 },
    { i: "sentiment",       x: 9, y: 6,  w: 3, h: 6,  minW: 2, minH: 4 },
    { i: "equity-curve",    x: 3, y: 12, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "open-positions",  x: 9, y: 12, w: 3, h: 7,  minW: 3, minH: 5 },
    { i: "portfolio-risk",  x: 0, y: 23, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "trade-log",       x: 6, y: 23, w: 6, h: 7,  minW: 3, minH: 5 },
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
      version: LAYOUT_VERSION,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        isLayoutLocked: state.isLayoutLocked,
        layouts: state.layouts,
      }),
      // When version bumps, discard old layout and use new defaults
      migrate: () => ({
        isLayoutLocked: true,
        layouts: DEFAULT_LAYOUTS,
      }),
    },
  ),
);
