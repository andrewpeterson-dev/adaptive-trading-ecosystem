"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  Settings,
  Save,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import {
  Surface,
  SurfaceBody,
  SurfaceHeader,
  SurfaceTitle,
} from "@/components/ui/surface";

interface RiskLimitsData {
  reduce_threshold: number;
  halt_threshold: number;
  daily_kill_threshold: number;
  weekly_kill_threshold: number;
  sector_cap: number;
  category_block_threshold: number;
  max_position_size: number;
  kill_switch_active: boolean;
}

function LimitRow({
  label,
  description,
  value,
  onChange,
  suffix,
  min,
  max,
  step,
}: {
  label: string;
  description: string;
  value: number;
  onChange: (v: number) => void;
  suffix?: string;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 border-b border-border/30 last:border-0">
      <div className="min-w-0">
        <div className="text-xs font-semibold text-foreground">{label}</div>
        <div className="text-[9px] text-muted-foreground">{description}</div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          min={min}
          max={max}
          step={step ?? 0.5}
          className="w-20 rounded-lg border border-border/75 bg-card px-2 py-1.5 text-xs font-mono text-right tabular-nums focus:outline-none focus:ring-2 focus:ring-ring/50"
        />
        {suffix && (
          <span className="text-[9px] text-muted-foreground font-mono">
            {suffix}
          </span>
        )}
      </div>
    </div>
  );
}

export function RiskLimitsConfig() {
  const [data, setData] = useState<RiskLimitsData>({
    reduce_threshold: -2,
    halt_threshold: -4,
    daily_kill_threshold: -7,
    weekly_kill_threshold: -10,
    sector_cap: 30,
    category_block_threshold: 30,
    max_position_size: 5,
    kill_switch_active: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const result = await apiFetch<RiskLimitsData>("/api/risk/advanced-limits");
      setData(result);
    } catch {
      // Use defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await apiFetch("/api/risk/advanced-limits", {
        method: "PUT",
        body: JSON.stringify(data),
        cacheTtlMs: 0,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setError(e?.message || "Failed to save limits.");
    } finally {
      setSaving(false);
    }
  };

  const toggleKillSwitch = () => {
    setData((prev) => ({ ...prev, kill_switch_active: !prev.kill_switch_active }));
  };

  if (loading) {
    return (
      <Surface>
        <SurfaceBody className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </SurfaceBody>
      </Surface>
    );
  }

  return (
    <Surface>
      <SurfaceHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Risk Limits Configuration</SurfaceTitle>
          </div>
          <div className="flex items-center gap-2">
            {saved && (
              <Badge variant="success" className="text-[9px] py-0.5">
                Saved
              </Badge>
            )}
            {error && (
              <Badge variant="danger" className="text-[9px] py-0.5">
                Error
              </Badge>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="app-button-primary text-xs px-3 py-1.5 rounded-lg"
            >
              {saving ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Save className="h-3 w-3" />
              )}
              Save
            </button>
          </div>
        </div>
      </SurfaceHeader>
      <SurfaceBody className="p-3">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Left Panel: Drawdown Thresholds */}
          <div className="app-inset p-3 space-y-0">
            <div className="flex items-center gap-2 pb-2 border-b border-border/40 mb-1">
              <Zap className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Drawdown Thresholds
              </span>
            </div>
            <LimitRow
              label="Reduce Size"
              description="Cut position sizing at this drawdown"
              value={data.reduce_threshold}
              onChange={(v) =>
                setData((p) => ({ ...p, reduce_threshold: v }))
              }
              suffix="%"
              min={-20}
              max={0}
            />
            <LimitRow
              label="Halt New Trades"
              description="Stop opening new positions"
              value={data.halt_threshold}
              onChange={(v) =>
                setData((p) => ({ ...p, halt_threshold: v }))
              }
              suffix="%"
              min={-30}
              max={0}
            />
            <LimitRow
              label="Daily Kill"
              description="Close all positions for the day"
              value={data.daily_kill_threshold}
              onChange={(v) =>
                setData((p) => ({ ...p, daily_kill_threshold: v }))
              }
              suffix="%"
              min={-50}
              max={0}
            />
            <LimitRow
              label="Weekly Kill"
              description="Halt all trading for the week"
              value={data.weekly_kill_threshold}
              onChange={(v) =>
                setData((p) => ({ ...p, weekly_kill_threshold: v }))
              }
              suffix="%"
              min={-50}
              max={0}
            />
          </div>

          {/* Right Panel: Concentration & Safety */}
          <div className="app-inset p-3 space-y-0">
            <div className="flex items-center gap-2 pb-2 border-b border-border/40 mb-1">
              <ShieldAlert className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Concentration & Safety
              </span>
            </div>
            <LimitRow
              label="Sector Cap"
              description="Max allocation to any single sector"
              value={data.sector_cap}
              onChange={(v) => setData((p) => ({ ...p, sector_cap: v }))}
              suffix="%"
              min={5}
              max={100}
              step={5}
            />
            <LimitRow
              label="Category Block"
              description="Block strategies scoring below this"
              value={data.category_block_threshold}
              onChange={(v) =>
                setData((p) => ({ ...p, category_block_threshold: v }))
              }
              suffix="/100"
              min={0}
              max={100}
              step={5}
            />
            <LimitRow
              label="Max Position Size"
              description="Maximum % of portfolio per position"
              value={data.max_position_size}
              onChange={(v) =>
                setData((p) => ({ ...p, max_position_size: v }))
              }
              suffix="%"
              min={1}
              max={50}
              step={1}
            />

            {/* Kill Switch */}
            <div className="flex items-center justify-between gap-3 py-2.5 mt-1 border-t border-border/40">
              <div className="min-w-0">
                <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  {data.kill_switch_active ? (
                    <ShieldAlert className="h-3.5 w-3.5 text-red-400" />
                  ) : (
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
                  )}
                  Kill Switch
                </div>
                <div className="text-[9px] text-muted-foreground">
                  {data.kill_switch_active
                    ? "Trading halted — all bots stopped"
                    : "Trading active — bots running normally"}
                </div>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={data.kill_switch_active}
                onClick={toggleKillSwitch}
                className={`
                  relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent
                  transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
                  ${data.kill_switch_active ? "bg-red-500" : "bg-emerald-500"}
                `}
              >
                <span
                  className={`
                    pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0
                    transition duration-200 ease-in-out
                    ${data.kill_switch_active ? "translate-x-5" : "translate-x-0"}
                  `}
                />
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-500/25 bg-red-500/8 px-3 py-2 text-xs text-red-300">
            <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
            {error}
          </div>
        )}
      </SurfaceBody>
    </Surface>
  );
}
