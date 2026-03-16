"use client";

import React, { useState } from "react";
import { ChevronDown } from "lucide-react";

interface AccordionSectionProps {
  title: string;
  defaultOpen?: boolean;
  badge?: string;
  borderColor?: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}

export function AccordionSection({
  title,
  defaultOpen = false,
  badge,
  borderColor,
  icon,
  children,
}: AccordionSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={`app-panel overflow-hidden ${borderColor ? `border-l-4 ${borderColor}` : ""}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between bg-slate-950/[0.03] px-5 py-4 text-left transition-colors hover:bg-slate-950/[0.05] dark:bg-white/[0.03] dark:hover:bg-white/[0.05]"
      >
        <div className="flex items-center gap-2">
          {icon && <span className="text-muted-foreground">{icon}</span>}
          <span className="app-label">
            {title}
          </span>
          {badge && (
            <span className="app-pill px-2.5 py-1 font-mono tracking-normal text-primary">
              {badge}
            </span>
          )}
        </div>
        <ChevronDown
          className={`h-3.5 w-3.5 text-muted-foreground transition-transform duration-150 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open && <div className="px-5 py-5 space-y-4">{children}</div>}
    </div>
  );
}
