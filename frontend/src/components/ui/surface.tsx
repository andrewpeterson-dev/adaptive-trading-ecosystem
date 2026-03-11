import * as React from "react";
import { cn } from "@/lib/utils";

export function Surface({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>) {
  return <section className={cn("app-panel", className)}>{children}</section>;
}

export function SurfaceHeader({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("app-section-header", className)}>{children}</div>;
}

export function SurfaceTitle({
  className,
  children,
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("app-section-title", className)}>{children}</h3>;
}

export function SurfaceBody({
  className,
  children,
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4 md:p-5", className)}>{children}</div>;
}
