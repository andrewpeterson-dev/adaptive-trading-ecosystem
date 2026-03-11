import * as React from "react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div className={cn("app-empty", className)}>
      {icon && <div className="app-empty-icon">{icon}</div>}
      <div className="space-y-1.5">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description && (
          <p className="max-w-md text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  );
}
