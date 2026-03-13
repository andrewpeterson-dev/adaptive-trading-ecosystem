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
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="max-w-[52rem] space-y-3">
          {eyebrow && <p className="app-kicker">{eyebrow}</p>}

          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[2rem] font-semibold leading-tight tracking-tight text-foreground sm:text-[2.35rem]">
              {title}
            </h1>
            {badge}
          </div>

          {description && (
            <p className="max-w-[44rem] text-sm leading-6 text-muted-foreground sm:text-[15px]">
              {description}
            </p>
          )}

          {meta && (
            <div className="flex flex-wrap items-center gap-2.5 text-sm text-muted-foreground">
              {meta}
            </div>
          )}
        </div>

        {actions && (
          <div className="flex flex-wrap items-center gap-2.5 xl:justify-end">
            {actions}
          </div>
        )}
      </div>
    </section>
  );
}
