"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { LayoutItem, Layouts } from "@/components/dashboard/GridLayout";

// ---------------------------------------------------------------------------
// Default grid layout (12-column, rowHeight 40px)
// Chart is now a hero element ABOVE the grid — removed from layout.
// ---------------------------------------------------------------------------

/** Bumped LAYOUT_VERSION to bust stale localStorage when defaults change. */
const LAYOUT_VERSION = 3;

const DEFAULT_LAYOUTS: Layouts = {
  lg: [
    // Left column: AI intelligence stack
    { i: "strategy",        x: 0, y: 0,  w: 3, h: 8,  minW: 2, minH: 5 },
    { i: "ai-reasoning",    x: 0, y: 8,  w: 3, h: 8,  minW: 2, minH: 5 },
    { i: "ai-scanner",      x: 0, y: 16, w: 3, h: 7,  minW: 2, minH: 4 },
    // Center column: secondary analytics
    { i: "equity-curve",    x: 3, y: 0,  w: 6, h: 8,  minW: 3, minH: 5 },
    { i: "portfolio-risk",  x: 3, y: 8,  w: 6, h: 7,  minW: 3, minH: 5 },
    // Right column: metrics + positions
    { i: "risk-metrics",    x: 9, y: 0,  w: 3, h: 6,  minW: 2, minH: 4 },
    { i: "sentiment",       x: 9, y: 6,  w: 3, h: 6,  minW: 2, minH: 4 },
    { i: "open-positions",  x: 9, y: 12, w: 3, h: 7,  minW: 3, minH: 5 },
    // Full-width bottom row
    { i: "trade-log",       x: 0, y: 23, w: 12, h: 7, minW: 6, minH: 5 },
  ],
  md: [
    { i: "strategy",        x: 0, y: 0,  w: 6, h: 7,  minW: 3, minH: 4 },
    { i: "ai-reasoning",    x: 6, y: 0,  w: 6, h: 7,  minW: 3, minH: 4 },
    { i: "ai-scanner",      x: 0, y: 7,  w: 6, h: 6,  minW: 3, minH: 4 },
    { i: "risk-metrics",    x: 6, y: 7,  w: 6, h: 6,  minW: 3, minH: 4 },
    { i: "equity-curve",    x: 0, y: 13, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "sentiment",       x: 6, y: 13, w: 6, h: 6,  minW: 3, minH: 4 },
    { i: "open-positions",  x: 0, y: 20, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "portfolio-risk",  x: 6, y: 20, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "trade-log",       x: 0, y: 27, w: 12, h: 7, minW: 6, minH: 5 },
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
