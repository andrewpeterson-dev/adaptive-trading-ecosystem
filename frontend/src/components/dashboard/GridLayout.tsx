"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";

// ---------------------------------------------------------------------------
// Types (inline — @types/react-grid-layout v1 doesn't match RGL v2 runtime)
// ---------------------------------------------------------------------------

export interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  static?: boolean;
}

export type Layouts = Record<string, LayoutItem[]>;

interface DashboardGridProps {
  children: React.ReactNode;
  layouts: Layouts;
  isDraggable: boolean;
  isResizable: boolean;
  onLayoutChange: (layout: LayoutItem[], allLayouts: Layouts) => void;
}

// ---------------------------------------------------------------------------
// Component — wraps react-grid-layout's Responsive with width measurement
// ---------------------------------------------------------------------------

export function DashboardGrid({
  children,
  layouts,
  isDraggable,
  isResizable,
  onLayoutChange,
}: DashboardGridProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1200);
  // eslint-disable-next-line
  const [GridComponent, setGridComponent] = useState<React.ComponentType<any> | null>(null);

  // Dynamically import react-grid-layout on client
  useEffect(() => {
    import("react-grid-layout").then((mod) => {
      // eslint-disable-next-line
      const RGL = (mod as any).default ?? mod;
      setGridComponent(() => RGL.Responsive ?? RGL);
    });
  }, []);

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

  if (!GridComponent) {
    return <div ref={containerRef} style={{ minHeight: 400 }} />;
  }

  return (
    <div ref={containerRef}>
      <GridComponent
        className="layout"
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 768 }}
        cols={{ lg: 12, md: 12 }}
        rowHeight={40}
        margin={[16, 16]}
        containerPadding={[0, 0]}
        width={width}
        isDraggable={isDraggable}
        isResizable={isResizable}
        draggableHandle=".dashboard-panel-header"
        onLayoutChange={onLayoutChange}
        useCSSTransforms={false}
        compactType="vertical"
      >
        {children}
      </GridComponent>
    </div>
  );
}
