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
    <div className="inline-flex rounded-lg border border-border/50 overflow-hidden bg-muted/30">
      {modes.map((m) => {
        const active = assetMode === m.value;
        return (
          <button
            key={m.value}
            type="button"
            onClick={() => setAssetMode(m.value)}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-semibold transition-all ${
              active
                ? "bg-card text-foreground shadow-sm border-r border-border/50"
                : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            }`}
          >
            <m.icon className={`h-3.5 w-3.5 ${active ? "text-primary" : ""}`} />
            {m.label}
          </button>
        );
      })}
    </div>
  );
}
