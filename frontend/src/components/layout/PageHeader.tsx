import { RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: React.ReactNode;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
  updatedAt?: Date | null;
  onRefresh?: () => void;
  className?: string;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  badge,
  actions,
  meta,
  updatedAt,
  onRefresh,
  className,
}: PageHeaderProps) {
  const renderedMeta = meta ?? (updatedAt ? (
    <span className="app-pill font-mono tracking-normal">
      Updated {updatedAt.toLocaleTimeString()}
    </span>
  ) : null);

  const renderedActions = actions ?? (onRefresh ? (
    <button onClick={onRefresh} className="app-button-secondary">
      <RefreshCw className="h-4 w-4" />
      Refresh
    </button>
  ) : null);

  return (
    <section className={cn("app-hero", className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1 space-y-1.5">
          {eyebrow && <p className="app-kicker">{eyebrow}</p>}

          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-semibold leading-tight tracking-tight text-foreground sm:text-[1.75rem]">
              {title}
            </h1>
            {badge}
          </div>

          {description && (
            <p className="max-w-full text-[13px] leading-5 text-muted-foreground sm:max-w-[44rem]">
              {description}
            </p>
          )}

          {renderedMeta && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {renderedMeta}
            </div>
          )}
        </div>

        {renderedActions && (
          <div className="flex shrink-0 flex-wrap items-center gap-2.5">
            {renderedActions}
          </div>
        )}
      </div>
    </section>
  );
}
