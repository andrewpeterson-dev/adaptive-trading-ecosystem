import * as React from "react";
import { cn } from "@/lib/utils";

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
  indicatorClassName?: string;
}

export function Progress({
  className,
  value,
  indicatorClassName,
  ...props
}: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value));

  return (
    <div className={cn("app-progress-track", className)} {...props}>
      <div
        className={cn("app-progress-bar bg-primary", indicatorClassName)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
