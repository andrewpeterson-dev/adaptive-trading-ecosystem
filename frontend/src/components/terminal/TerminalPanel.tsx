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
    <div className={`terminal-panel h-full flex flex-col overflow-hidden ${className}`}>
      {/* Scanline overlay */}
      <div className="terminal-scanlines pointer-events-none absolute inset-0 z-10" />

      {/* Header bar */}
      <div className="terminal-header flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2.5">
          {/* Window dots */}
          <div className="flex items-center gap-[5px]">
            <span className="terminal-dot terminal-dot--red" />
            <span className="terminal-dot terminal-dot--yellow" />
            <span className="terminal-dot terminal-dot--green" />
          </div>
          <span className="terminal-separator" />
          {icon && <span className={accent}>{icon}</span>}
          <span className="terminal-title">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          {actions && <div className="flex items-center gap-1.5">{actions}</div>}
          <span className="terminal-cursor" />
        </div>
      </div>

      {/* Body */}
      <div className={`terminal-body flex-1 overflow-auto ${compact ? "p-3" : "p-4"}`}>
        {children}
      </div>
    </div>
  );
}
