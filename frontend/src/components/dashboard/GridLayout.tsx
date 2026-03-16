"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import { Responsive as ResponsiveGridLayout } from "react-grid-layout";

interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  static?: boolean;
}

type Layouts = Record<string, LayoutItem[]>;

interface DashboardGridProps {
  children: React.ReactNode;
  layouts: Layouts;
  isDraggable: boolean;
  isResizable: boolean;
  onLayoutChange: (layout: LayoutItem[], allLayouts: Layouts) => void;
}

export function DashboardGrid({
  children,
  layouts,
  isDraggable,
  isResizable,
  onLayoutChange,
}: DashboardGridProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1200);

  const updateWidth = useCallback(() => {
    if (containerRef.current) {
      setWidth(containerRef.current.clientWidth);
    }
  }, []);

  useEffect(() => {
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    if (containerRef.current) {
      observer.observe(containerRef.current);
    }
    return () => observer.disconnect();
  }, [updateWidth]);

  return (
    <div ref={containerRef}>
      <ResponsiveGridLayout
        className="layout"
        layouts={layouts as Record<string, ReactGridLayout.Layout[]>}
        breakpoints={{ lg: 1200, md: 768 }}
        cols={{ lg: 12, md: 12 }}
        rowHeight={40}
        margin={[16, 16] as [number, number]}
        containerPadding={[0, 0] as [number, number]}
        width={width}
        isDraggable={isDraggable}
        isResizable={isResizable}
        draggableHandle=".dashboard-panel-header"
        onLayoutChange={onLayoutChange as never}
        useCSSTransforms={false}
        compactType="vertical"
      >
        {children}
      </ResponsiveGridLayout>
    </div>
  );
}
