import { cn } from "@/lib/utils";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: React.ReactNode;
  badge?: React.ReactNode;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
  className?: string;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  badge,
  actions,
  meta,
  className,
}: PageHeaderProps) {
  return (
    <section className={cn("app-hero", className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-1.5">
          {eyebrow && <p className="app-kicker">{eyebrow}</p>}

          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl font-semibold leading-tight tracking-tight text-foreground sm:text-[1.75rem]">
              {title}
            </h1>
            {badge}
          </div>

          {description && (
            <p className="max-w-[44rem] text-[13px] leading-5 text-muted-foreground">
              {description}
            </p>
          )}

          {meta && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              {meta}
            </div>
          )}
        </div>

        {actions && (
          <div className="flex shrink-0 flex-wrap items-center gap-2.5">
            {actions}
          </div>
        )}
      </div>
    </section>
  );
}
