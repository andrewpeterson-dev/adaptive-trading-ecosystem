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
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl space-y-4">
          {eyebrow && <p className="app-kicker">{eyebrow}</p>}

          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-[2.5rem]">
              {title}
            </h1>
            {badge}
          </div>

          {description && (
            <p className="max-w-2xl text-sm leading-7 text-muted-foreground sm:text-[15px]">
              {description}
            </p>
          )}

          {meta && (
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              {meta}
            </div>
          )}
        </div>

        {actions && (
          <div className="flex flex-wrap items-center gap-3 lg:justify-end">
            {actions}
          </div>
        )}
      </div>
    </section>
  );
}
