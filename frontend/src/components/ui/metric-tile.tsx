import { cn } from "@/lib/utils";

interface MetricTileProps {
  label: string;
  value: string | number;
  subtitle?: string;
  sentiment?: "positive" | "negative" | "neutral";
  mono?: boolean;
  className?: string;
}

export function MetricTile({
  label,
  value,
  subtitle,
  sentiment,
  mono = true,
  className,
}: MetricTileProps) {
  return (
    <div className={cn("app-panel p-4", className)}>
      <p className="app-metric-label">{label}</p>
      <p
        className={cn(
          mono ? "app-metric-value-mono" : "app-metric-value",
          "mt-1",
          sentiment === "positive" && "text-positive",
          sentiment === "negative" && "text-negative"
        )}
      >
        {value}
      </p>
      {subtitle && (
        <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
      )}
    </div>
  );
}
