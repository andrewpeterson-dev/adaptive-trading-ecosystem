import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]",
  {
    variants: {
      variant: {
        neutral:
          "border-border/75 bg-muted/45 text-muted-foreground",
        primary:
          "border-primary/25 bg-primary/12 text-primary",
        positive:
          "border-emerald-500/25 bg-emerald-500/12 text-emerald-300",
        success:
          "border-emerald-500/25 bg-emerald-500/12 text-emerald-300",
        negative:
          "border-red-500/25 bg-red-500/12 text-red-200",
        danger:
          "border-red-500/25 bg-red-500/12 text-red-200",
        warning:
          "border-amber-500/25 bg-amber-500/12 text-amber-300",
        info:
          "border-sky-500/25 bg-sky-500/12 text-sky-300",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
