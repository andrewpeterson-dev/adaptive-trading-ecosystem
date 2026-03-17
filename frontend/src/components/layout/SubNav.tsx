"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface SubNavItem {
  href: string;
  label: string;
  icon?: LucideIcon;
}

export function SubNav({ items }: { items: SubNavItem[] }) {
  const pathname = usePathname();
  return (
    <div className="flex items-center gap-1 rounded-full border border-border/50 bg-muted/20 p-1 w-fit">
      {items.map((item) => {
        const Icon = item.icon;
        const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href + "/"));
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[13px] font-medium transition-colors",
              active
                ? "bg-primary/12 text-primary border border-primary/20"
                : "text-muted-foreground hover:text-foreground border border-transparent"
            )}
          >
            {Icon && <Icon className="h-3.5 w-3.5" />}
            {item.label}
          </Link>
        );
      })}
    </div>
  );
}
