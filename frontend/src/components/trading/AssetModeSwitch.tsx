"use client";

import React from "react";
import { BarChart3, Settings } from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";
import type { AssetMode } from "@/types/trading";

const modes: { value: AssetMode; label: string; icon: React.ElementType }[] = [
  { value: "stocks", label: "Stocks", icon: BarChart3 },
  { value: "options", label: "Options", icon: Settings },
];

export function AssetModeSwitch() {
  const assetMode = useTradeStore((s) => s.assetMode);
  const setAssetMode = useTradeStore((s) => s.setAssetMode);

  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-black/5 bg-white/75 p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)] dark:border-white/10 dark:bg-white/[0.05]">
      {modes.map((m) => {
        const active = assetMode === m.value;
        return (
          <button
            key={m.value}
            type="button"
            onClick={() => setAssetMode(m.value)}
            className={`flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold transition-all ${
              active
                ? "bg-foreground text-background shadow-[0_14px_28px_-20px_rgba(15,23,42,0.65)]"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <m.icon className="h-3.5 w-3.5" />
            {m.label}
          </button>
        );
      })}
    </div>
  );
}
