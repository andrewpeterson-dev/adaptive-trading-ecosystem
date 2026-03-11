import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn("app-skeleton rounded-md", className)}
    />
  );
}

export function SkeletonText({ className }: SkeletonProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  );
}

export function SkeletonCard({ className }: SkeletonProps) {
  return (
    <div className={cn("app-panel p-6 space-y-4", className)}>
      <Skeleton className="h-5 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  );
}

export function SkeletonChart({ className }: SkeletonProps) {
  return (
    <div className={cn("app-panel p-6 space-y-4", className)}>
      <Skeleton className="h-5 w-1/4" />
      <Skeleton className="h-48 w-full" />
    </div>
  );
}

export function SkeletonTableRow({ className }: SkeletonProps) {
  return (
    <div className={cn("flex items-center gap-4 py-3", className)}>
      <Skeleton className="h-4 w-20" />
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-4 w-16" />
      <Skeleton className="h-4 w-24" />
    </div>
  );
}
