"use client";

import React from "react";
import type { RiskGaugeConfig } from "@/types/risk";

function gaugeColor(ratio: number): string {
  if (ratio < 0.5) return "text-emerald-400";
  if (ratio < 0.7) return "text-amber-400";
  return "text-red-400";
}

function arcColor(ratio: number): string {
  if (ratio < 0.5) return "#10b981";
  if (ratio < 0.7) return "#f59e0b";
  return "#ef4444";
}

export function RiskGauge({ config }: { config: RiskGaugeConfig }) {
  const ratio = config.limit > 0 ? Math.min(config.current / config.limit, 1) : 0;
  const angle = ratio * 180;
  const color = gaugeColor(ratio);
  const stroke = arcColor(ratio);

  const cx = 60;
  const cy = 55;
  const r = 40;
  const startAngle = Math.PI;
  const endAngle = Math.PI - (angle * Math.PI) / 180;

  const startX = cx + r * Math.cos(startAngle);
  const startY = cy - r * Math.sin(startAngle);
  const endX = cx + r * Math.cos(endAngle);
  const endY = cy - r * Math.sin(endAngle);

  const largeArc = angle > 180 ? 1 : 0;
  const arcPath = `M ${startX} ${startY} A ${r} ${r} 0 ${largeArc} 1 ${endX} ${endY}`;
  const bgPath = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;

  return (
    <div className="app-card flex flex-col items-center p-4">
      <div className="app-label mb-2">{config.label}</div>
      <svg width="120" height="70" viewBox="0 0 120 70">
        <path
          d={bgPath}
          fill="none"
          stroke="hsl(var(--surface-3))"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {ratio > 0 && (
          <path
            d={arcPath}
            fill="none"
            stroke={stroke}
            strokeWidth="8"
            strokeLinecap="round"
          />
        )}
      </svg>
      <div className={`-mt-1 text-lg font-mono font-bold tabular-nums ${color}`}>
        {config.unit === "%"
          ? `${(config.current * 100).toFixed(1)}%`
          : config.current.toFixed(0)}
      </div>
      <div className="mt-0.5 text-[11px] text-muted-foreground">
        of{" "}
        {config.unit === "%"
          ? `${(config.limit * 100).toFixed(0)}%`
          : config.limit.toFixed(0)}{" "}
        {config.unit !== "%" ? config.unit : ""} limit
      </div>
    </div>
  );
}
