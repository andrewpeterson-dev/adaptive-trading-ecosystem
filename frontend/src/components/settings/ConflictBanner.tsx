"use client";

import { AlertTriangle } from "lucide-react";

interface Conflict {
  type: string;
  message: string;
  affected_ids: number[];
}

interface ConflictBannerProps {
  conflicts: Conflict[];
}

export function ConflictBanner({ conflicts }: ConflictBannerProps) {
  if (!conflicts || conflicts.length === 0) return null;

  return (
    <div className="space-y-2">
      {conflicts.map((conflict, i) => (
        <div
          key={i}
          className="flex items-start gap-2.5 rounded-lg border border-amber-400/20 bg-amber-400/5 px-4 py-3"
        >
          <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
          <p className="text-sm text-amber-300">{conflict.message}</p>
        </div>
      ))}
    </div>
  );
}
