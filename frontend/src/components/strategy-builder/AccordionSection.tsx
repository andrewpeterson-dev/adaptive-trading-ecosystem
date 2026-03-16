"use client";

import React, { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

type AccordionAccent = "green" | "red" | "orange" | "slate" | "blue";

const ACCENT_STYLES: Record<AccordionAccent, {
  border: string;
  headerBg: string;
  headerHover: string;
  iconColor: string;
  badgeBg: string;
  badgeText: string;
  bodyBorder: string;
}> = {
  green: {
    border: "border-l-emerald-500",
    headerBg: "bg-emerald-500/[0.04] dark:bg-emerald-400/[0.04]",
    headerHover: "hover:bg-emerald-500/[0.07] dark:hover:bg-emerald-400/[0.07]",
    iconColor: "text-emerald-500",
    badgeBg: "bg-emerald-500/10 border-emerald-500/20",
    badgeText: "text-emerald-400",
    bodyBorder: "border-t-emerald-500/10",
  },
  red: {
    border: "border-l-red-500",
    headerBg: "bg-red-500/[0.04] dark:bg-red-400/[0.04]",
    headerHover: "hover:bg-red-500/[0.07] dark:hover:bg-red-400/[0.07]",
    iconColor: "text-red-500",
    badgeBg: "bg-red-500/10 border-red-500/20",
    badgeText: "text-red-400",
    bodyBorder: "border-t-red-500/10",
  },
  orange: {
    border: "border-l-amber-500",
    headerBg: "bg-amber-500/[0.04] dark:bg-amber-400/[0.04]",
    headerHover: "hover:bg-amber-500/[0.07] dark:hover:bg-amber-400/[0.07]",
    iconColor: "text-amber-500",
    badgeBg: "bg-amber-500/10 border-amber-500/20",
    badgeText: "text-amber-400",
    bodyBorder: "border-t-amber-500/10",
  },
  slate: {
    border: "border-l-slate-400",
    headerBg: "bg-slate-950/[0.03] dark:bg-white/[0.03]",
    headerHover: "hover:bg-slate-950/[0.05] dark:hover:bg-white/[0.05]",
    iconColor: "text-muted-foreground",
    badgeBg: "bg-muted/60 border-border/60",
    badgeText: "text-muted-foreground",
    bodyBorder: "border-t-border/30",
  },
  blue: {
    border: "border-l-blue-500",
    headerBg: "bg-blue-500/[0.04] dark:bg-blue-400/[0.04]",
    headerHover: "hover:bg-blue-500/[0.07] dark:hover:bg-blue-400/[0.07]",
    iconColor: "text-blue-500",
    badgeBg: "bg-blue-500/10 border-blue-500/20",
    badgeText: "text-blue-400",
    bodyBorder: "border-t-blue-500/10",
  },
};

interface AccordionSectionProps {
  title: string;
  defaultOpen?: boolean;
  badge?: string;
  /** @deprecated Use `accent` instead */
  borderColor?: string;
  accent?: AccordionAccent;
  icon?: React.ReactNode;
  subtitle?: string;
  children: React.ReactNode;
}

export function AccordionSection({
  title,
  defaultOpen = false,
  badge,
  borderColor,
  accent = "slate",
  icon,
  subtitle,
  children,
}: AccordionSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const styles = ACCENT_STYLES[accent];

  return (
    <div className={cn("app-panel overflow-hidden border-l-4", styles.border)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "w-full flex items-center justify-between px-5 py-4 text-left transition-colors",
          styles.headerBg,
          styles.headerHover
        )}
      >
        <div className="flex items-center gap-2.5">
          {icon && <span className={styles.iconColor}>{icon}</span>}
          <div className="flex flex-col">
            <span className="app-label">{title}</span>
            {subtitle && (
              <span className="text-[11px] text-muted-foreground/70 mt-0.5">{subtitle}</span>
            )}
          </div>
          {badge && (
            <span className={cn(
              "px-2.5 py-1 rounded-full border text-[11px] font-semibold font-mono tracking-normal",
              styles.badgeBg,
              styles.badgeText
            )}>
              {badge}
            </span>
          )}
        </div>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-muted-foreground transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>
      {open && (
        <div className={cn("px-5 py-5 space-y-4 border-t", styles.bodyBorder)}>
          {children}
        </div>
      )}
    </div>
  );
}
