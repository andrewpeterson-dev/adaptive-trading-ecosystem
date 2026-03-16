import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return <div className={cn("app-skeleton rounded-lg", className)} />;
}

export function MetricSkeleton({ className }: SkeletonProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-8 w-32" />
    </div>
  );
}

export function CardSkeleton({ className }: SkeletonProps) {
  return (
    <div className={cn("app-panel p-5 space-y-4", className)}>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-6 w-48" />
      <div className="space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/4" />
      </div>
    </div>
  );
}

export function TableRowSkeleton({ cols = 5 }: { cols?: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-full" />
        </td>
      ))}
    </tr>
  );
}

export function ChartSkeleton({ className }: SkeletonProps) {
  return (
    <div className={cn("app-panel flex items-center justify-center", className)} style={{ minHeight: 300 }}>
      <div className="space-y-3 text-center">
        <Skeleton className="mx-auto h-32 w-full max-w-md rounded-xl" />
        <Skeleton className="mx-auto h-3 w-24" />
      </div>
    </div>
  );
}

// Legacy aliases — keep for backward compatibility with existing imports
export { CardSkeleton as SkeletonCard };
export { ChartSkeleton as SkeletonChart };

export function SkeletonText({ className }: SkeletonProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}

export function SkeletonTableRow({ className, cols = 4 }: SkeletonProps & { cols?: number }) {
  return (
    <div className={cn("flex items-center gap-4 py-3", className)}>
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} className="h-4 flex-1" />
      ))}
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
      <ChartSkeleton />
    </div>
  );
}
