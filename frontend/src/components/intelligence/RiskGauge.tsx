"use client";

import { useEffect, useState } from "react";
import { ShieldAlert } from "lucide-react";
import { getRiskScore, type RiskScore } from "@/lib/reasoning-api";

export function RiskGauge() {
  const [data, setData] = useState<RiskScore | null>(null);

  useEffect(() => {
    getRiskScore().then(setData).catch(() => {});
    const interval = setInterval(() => {
      getRiskScore().then(setData).catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  const score = data?.score ?? 0;
  const level = data?.level ?? "low";
  const colorMap = {
    low: "text-emerald-400 border-emerald-400/20 bg-emerald-400/8",
    medium: "text-amber-400 border-amber-400/20 bg-amber-400/8",
    high: "text-rose-400 border-rose-400/20 bg-rose-400/8",
  };
  const barColor = {
    low: "bg-emerald-400",
    medium: "bg-amber-400",
    high: "bg-rose-400",
  };
  const vix = data?.components.vix as { value?: number } | undefined;
  const fearGreed = data?.components.fear_greed as { value?: number } | undefined;

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <ShieldAlert className="h-3.5 w-3.5 text-sky-400" />
        Market Risk Score
      </div>

      <div className="mt-4 flex items-end gap-4">
        <div className={`rounded-2xl border px-4 py-3 ${colorMap[level]}`}>
          <div className="text-3xl font-bold tabular-nums">{Math.round(score)}</div>
          <div className="mt-1 text-xs font-semibold uppercase tracking-[0.16em]">
            {level}
          </div>
        </div>

        <div className="flex-1">
          <div className="h-3 w-full overflow-hidden rounded-full bg-muted/30">
            <div
              className={`h-full rounded-full transition-all duration-700 ${barColor[level]}`}
              style={{ width: `${Math.min(100, score)}%` }}
            />
          </div>
          <div className="mt-2 flex justify-between text-[10px] text-muted-foreground">
            <span>0 — Calm</span>
            <span>100 — Crisis</span>
          </div>
        </div>
      </div>

      {data ? (
        <div className="mt-4 grid grid-cols-3 gap-3">
          {vix ? (
            <div className="rounded-2xl border border-border/60 bg-muted/10 px-3 py-2.5">
              <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">VIX</div>
              <div className="mt-1 text-sm font-semibold text-foreground">
                {vix.value?.toFixed(1) ?? "—"}
              </div>
            </div>
          ) : null}
          {fearGreed ? (
            <div className="rounded-2xl border border-border/60 bg-muted/10 px-3 py-2.5">
              <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Fear/Greed</div>
              <div className="mt-1 text-sm font-semibold text-foreground">
                {fearGreed.value?.toFixed(0) ?? "—"}
              </div>
            </div>
          ) : null}
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-3 py-2.5">
            <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Active Events</div>
            <div className="mt-1 text-sm font-semibold text-foreground">{data.active_events}</div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
