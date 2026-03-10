"use client";

import React from "react";
import { useTradeStore } from "@/stores/trade-store";
import type { AssetMode } from "@/types/trading";

const modes: { value: AssetMode; label: string }[] = [
  { value: "stocks", label: "Stocks" },
  { value: "options", label: "Options" },
];

export function AssetModeSwitch() {
  const assetMode = useTradeStore((s) => s.assetMode);
  const setAssetMode = useTradeStore((s) => s.setAssetMode);

  return (
    <div className="inline-flex rounded-md border border-border/50 overflow-hidden">
      {modes.map((m) => (
        <button
          key={m.value}
          type="button"
          onClick={() => setAssetMode(m.value)}
          className={`px-3 py-1.5 text-xs font-medium transition-colors ${
            assetMode === m.value
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground hover:text-foreground"
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}
