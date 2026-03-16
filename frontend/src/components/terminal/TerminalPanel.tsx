"use client";

interface TerminalPanelProps {
  title: string;
  icon?: React.ReactNode;
  accent?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  compact?: boolean;
  className?: string;
}

export function TerminalPanel({ title, icon, accent = "text-sky-400", children, actions, compact = false, className = "" }: TerminalPanelProps) {
  return (
    <div className={`h-full flex flex-col rounded-2xl border border-border/60 bg-card shadow-sm overflow-hidden ${className}`}>
      <div className="flex items-center justify-between gap-2 border-b border-border/40 px-4 py-2.5 shrink-0">
        <div className="flex items-center gap-2">
          {icon && <span className={accent}>{icon}</span>}
          <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{title}</span>
        </div>
        {actions && <div className="flex items-center gap-1.5">{actions}</div>}
      </div>
      <div className={`flex-1 overflow-auto ${compact ? "p-3" : "p-4"}`}>
        {children}
      </div>
    </div>
  );
}
