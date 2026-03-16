"use client";

import React, { useState, useCallback } from "react";
import { Settings, Maximize2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface PanelContainerProps {
  children: React.ReactNode;
  className?: string;
}

function PanelContainer({ children, className }: PanelContainerProps) {
  return (
    <div className={cn("app-panel rounded-xl h-full flex flex-col overflow-hidden", className)}>
      {children}
    </div>
  );
}

interface PanelHeaderProps {
  title: string;
  icon?: React.ComponentType<{ className?: string }>;
  onRefresh?: () => void;
  headerRight?: React.ReactNode;
}

function PanelHeader({ title, icon: Icon, onRefresh, headerRight }: PanelHeaderProps) {
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = useCallback(() => {
    if (!onRefresh || isRefreshing) return;
    setIsRefreshing(true);
    onRefresh();
    setTimeout(() => setIsRefreshing(false), 600);
  }, [onRefresh, isRefreshing]);

  return (
    <div
      className="dashboard-panel-header group/header flex h-9 shrink-0 items-center justify-between px-3 py-2 select-none cursor-grab active:cursor-grabbing"
    >
      <div className="flex items-center gap-1.5 min-w-0">
        {Icon && <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground truncate">
          {title}
        </span>
      </div>

      <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover/header:opacity-100">
        {headerRight}
        {onRefresh && (
          <button
            type="button"
            onClick={handleRefresh}
            className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-foreground/5 hover:text-muted-foreground"
          >
            <RefreshCw className={cn("h-3 w-3", isRefreshing && "animate-spin")} />
          </button>
        )}
        <button
          type="button"
          className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-foreground/5 hover:text-muted-foreground"
        >
          <Maximize2 className="h-3 w-3" />
        </button>
        <button
          type="button"
          className="flex h-6 w-6 items-center justify-center rounded-md text-muted-foreground/60 transition-colors hover:bg-foreground/5 hover:text-muted-foreground"
        >
          <Settings className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

interface PanelBodyProps {
  children: React.ReactNode;
  noPadding?: boolean;
  className?: string;
}

function PanelBody({ children, noPadding, className }: PanelBodyProps) {
  return (
    <div className={cn("flex-1 min-h-0 overflow-y-auto", !noPadding && "p-4", className)}>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Composed component
// ---------------------------------------------------------------------------

interface DashboardPanelProps {
  title: string;
  icon?: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  onRefresh?: () => void;
  className?: string;
  headerRight?: React.ReactNode;
  noPadding?: boolean;
}

function DashboardPanel({
  title,
  icon,
  children,
  onRefresh,
  className,
  headerRight,
  noPadding,
}: DashboardPanelProps) {
  return (
    <PanelContainer className={className}>
      <PanelHeader
        title={title}
        icon={icon}
        onRefresh={onRefresh}
        headerRight={headerRight}
      />
      <PanelBody noPadding={noPadding}>
        {children}
      </PanelBody>
    </PanelContainer>
  );
}

export { DashboardPanel, PanelContainer, PanelHeader, PanelBody };
export type { DashboardPanelProps };
