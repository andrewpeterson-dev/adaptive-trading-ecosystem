"use client";

import React, { useState, useCallback, useRef, useEffect } from "react";
import { Lock, Unlock, RotateCcw } from "lucide-react";
import dynamic from "next/dynamic";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const RGL = dynamic(() => import("react-grid-layout").then((m) => (m as any).default || m), { ssr: false }) as any;

interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
}

const STORAGE_KEY = "bot-terminal-layout-v2";

const DEFAULT_LAYOUT: LayoutItem[] = [
  { i: "performance", x: 0, y: 0, w: 8, h: 3, minW: 4, minH: 2 },
  { i: "capital", x: 8, y: 0, w: 2, h: 3, minW: 2, minH: 2 },
  { i: "settings", x: 10, y: 0, w: 2, h: 3, minW: 2, minH: 2 },
  { i: "chart", x: 0, y: 3, w: 8, h: 8, minW: 4, minH: 5 },
  { i: "positions", x: 8, y: 3, w: 4, h: 4, minW: 2, minH: 3 },
  { i: "risk", x: 8, y: 7, w: 2, h: 4, minW: 2, minH: 3 },
  { i: "logic", x: 10, y: 7, w: 2, h: 4, minW: 2, minH: 3 },
  { i: "universe", x: 0, y: 11, w: 4, h: 3, minW: 2, minH: 2 },
  { i: "tradelog", x: 4, y: 11, w: 8, h: 5, minW: 4, minH: 3 },
  { i: "equity", x: 0, y: 14, w: 4, h: 4, minW: 3, minH: 3 },
];

interface DashboardLayoutProps {
  children: Record<string, React.ReactNode>;
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [locked, setLocked] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1200);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      for (const entry of entries) setWidth(entry.contentRect.width);
    });
    obs.observe(containerRef.current);
    setWidth(containerRef.current.clientWidth);
    return () => obs.disconnect();
  }, []);

  const [layout, setLayout] = useState<LayoutItem[]>(() => {
    if (typeof window === "undefined") return DEFAULT_LAYOUT;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return JSON.parse(saved);
    } catch {}
    return DEFAULT_LAYOUT;
  });

  const handleLayoutChange = useCallback((newLayout: LayoutItem[]) => {
    setLayout(newLayout);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(newLayout)); } catch {}
  }, []);

  const handleReset = useCallback(() => {
    setLayout(DEFAULT_LAYOUT);
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
  }, []);

  const activeKeys = Object.keys(children);
  const filteredLayout = layout.filter((item) => activeKeys.includes(item.i));

  if (!mounted) {
    return (
      <div ref={containerRef} className="grid grid-cols-1 gap-3 xl:grid-cols-2">
        {activeKeys.map((key) => (
          <div key={key}>{children[key]}</div>
        ))}
      </div>
    );
  }

  const gridItems = activeKeys.map((key) => (
    <div key={key} className="overflow-hidden">
      {children[key]}
    </div>
  ));

  return (
    <div ref={containerRef} className="relative">
      <div className="mb-3 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => setLocked(!locked)}
          className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[11px] font-semibold transition-all ${
            locked
              ? "border-border/50 bg-muted/20 text-muted-foreground hover:text-foreground"
              : "border-sky-400/40 bg-sky-400/10 text-sky-400 shadow-[0_0_12px_-4px_rgba(56,189,248,0.3)]"
          }`}
        >
          {locked ? <Lock className="h-3 w-3" /> : <Unlock className="h-3 w-3" />}
          {locked ? "Unlock Layout" : "Editing Layout"}
        </button>
        {!locked && (
          <button type="button" onClick={handleReset} className="flex items-center gap-1 rounded-lg border border-border/50 bg-muted/20 px-3 py-1.5 text-[11px] font-semibold text-muted-foreground hover:text-foreground transition-colors">
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
        )}
      </div>

      <RGL
        layout={filteredLayout}
        cols={12}
        rowHeight={40}
        width={width}
        margin={[10, 10]}
        containerPadding={[0, 0]}
        isDraggable={!locked}
        isResizable={!locked}
        draggableHandle=".drag-handle"
        onLayoutChange={handleLayoutChange}
        useCSSTransforms={false}
      >
        {gridItems}
      </RGL>
    </div>
  );
}
