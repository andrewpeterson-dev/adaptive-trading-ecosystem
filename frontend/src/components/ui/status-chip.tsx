import { cn } from "@/lib/utils";

type ChipVariant = "positive" | "warning" | "danger" | "info" | "neutral" | "live" | "paper";

const variantClasses: Record<ChipVariant, string> = {
  positive: "border-emerald-500/25 bg-emerald-500/12 text-emerald-400",
  warning: "border-amber-500/25 bg-amber-500/12 text-amber-400",
  danger: "border-red-500/25 bg-red-500/12 text-red-300",
  info: "border-sky-500/25 bg-sky-500/12 text-sky-300",
  neutral: "border-border/75 bg-muted/45 text-muted-foreground",
  live: "border-emerald-500/25 bg-emerald-500/12 text-emerald-400",
  paper: "border-amber-500/25 bg-amber-500/12 text-amber-600 dark:text-amber-400",
};

interface StatusChipProps {
  variant: ChipVariant;
  label: string;
  pulse?: boolean;
  icon?: React.ReactNode;
  className?: string;
}

export function StatusChip({ variant, label, pulse, icon, className }: StatusChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-[11px] font-bold uppercase tracking-[0.14em]",
        variantClasses[variant],
        className
      )}
    >
      {pulse && (
        <span
          className={cn(
            "h-2 w-2 rounded-full animate-pulse-dot",
            variant === "live" || variant === "positive" ? "bg-emerald-400" : "bg-amber-500"
          )}
        />
      )}
      {icon}
      {label}
    </span>
  );
}
