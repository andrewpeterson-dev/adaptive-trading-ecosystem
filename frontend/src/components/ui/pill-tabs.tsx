"use client";

import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface PillTab {
  key: string;
  label: string;
  icon?: LucideIcon;
}

interface PillTabsProps {
  tabs: PillTab[];
  activeKey: string;
  onChange: (key: string) => void;
  className?: string;
}

export function PillTabs({ tabs, activeKey, onChange, className }: PillTabsProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-1 rounded-full border border-border/50 bg-muted/20 p-1 w-fit",
        className
      )}
      role="tablist"
    >
      {tabs.map((tab) => {
        const active = activeKey === tab.key;
        const Icon = tab.icon;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] font-medium transition-colors",
              active
                ? "bg-primary/12 text-primary border border-primary/20"
                : "text-muted-foreground hover:text-foreground border border-transparent"
            )}
          >
            {Icon && <Icon className="h-3.5 w-3.5" />}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
