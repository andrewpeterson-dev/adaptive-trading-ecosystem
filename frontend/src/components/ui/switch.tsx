import * as React from "react";
import { cn } from "@/lib/utils";

interface SwitchProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  checked: boolean;
}

export function Switch({
  checked,
  className,
  ...props
}: SwitchProps) {
  return (
    <button
      type="button"
      aria-pressed={checked}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 rounded-full border transition-colors",
        checked
          ? "border-primary/35 bg-primary/85"
          : "border-border/80 bg-muted/80",
        className
      )}
      {...props}
    >
      <span
        className={cn(
          "absolute top-0.5 h-4.5 w-4.5 rounded-full bg-white shadow-sm transition-transform",
          checked ? "translate-x-[1.3rem]" : "translate-x-0.5"
        )}
      />
    </button>
  );
}
