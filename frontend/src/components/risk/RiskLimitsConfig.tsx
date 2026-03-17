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
import { useToast } from "@/components/ui/toast";
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

function LimitRowSkeleton() {
  return (
    <div className="flex items-center justify-between gap-3 py-2 border-b border-border/30 last:border-0">
      <div className="space-y-1 min-w-0">
        <div className="app-skeleton h-3 w-28 rounded-full" />
        <div className="app-skeleton h-2 w-36 rounded-full" />
      </div>
      <div className="app-skeleton h-8 w-24 rounded-lg shrink-0" />
    </div>
  );
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
  id,
}: {
  label: string;
  description: string;
  value: number;
  onChange: (v: number) => void;
  suffix?: string;
  min?: number;
  max?: number;
  step?: number;
  id: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 border-b border-border/30 last:border-0 group">
      <div className="min-w-0">
        <label
          htmlFor={id}
          className="text-xs font-semibold text-foreground cursor-pointer"
        >
          {label}
        </label>
        <div className="text-[10px] text-muted-foreground mt-0.5">{description}</div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <input
          id={id}
          type="number"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          min={min}
          max={max}
          step={step ?? 0.5}
          aria-label={label}
          className="w-20 rounded-lg border bg-card px-2 py-1.5 text-xs font-mono text-right tabular-nums outline-none
            transition-all duration-150
            border-border/75
            hover:border-ring/30
            focus:border-ring/60 focus:ring-2 focus:ring-ring/20 focus:ring-offset-0
            text-foreground"
        />
        {suffix && (
          <span className="text-[10px] text-muted-foreground font-mono w-6">
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
  const { toast } = useToast();

  const fetchData = useCallback(async () => {
    try {
      // Fetch both basic limits and drawdown thresholds to populate config
      const [limitsRes, drawdownRes] = await Promise.allSettled([
        apiFetch<Record<string, any>>("/api/risk/limits"),
        apiFetch<Record<string, any>>("/api/risk/drawdown-status"),
      ]);
      const limits = limitsRes.status === "fulfilled" ? limitsRes.value : {};
      const drawdown = drawdownRes.status === "fulfilled" ? drawdownRes.value : {};
      const t = drawdown.thresholds || {};
      setData({
        reduce_threshold: t.drawdown_reduce_pct ?? -2,
        halt_threshold: t.drawdown_halt_pct ?? -4,
        daily_kill_threshold: t.drawdown_kill_pct ?? -7,
        weekly_kill_threshold: t.weekly_drawdown_kill_pct ?? -10,
        sector_cap: limits.sector_concentration_limit ?? 30,
        category_block_threshold: limits.category_block_threshold ?? 30,
        max_position_size: (limits.max_position_size_pct ?? 0.25) * 100,
        kill_switch_active: limits.kill_switch_active ?? false,
      });
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
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to save limits.");
    } finally {
      setSaving(false);
    }
  };

  const toggleKillSwitch = async () => {
    const newValue = !data.kill_switch_active;
    setData((prev) => ({ ...prev, kill_switch_active: newValue }));
    try {
      await apiFetch("/api/risk/advanced-limits", {
        method: "PUT",
        body: JSON.stringify({ kill_switch_active: newValue }),
        cacheTtlMs: 0,
      });
      toast(
        newValue ? "Kill switch activated — all trading halted" : "Kill switch deactivated — trading resumed",
        newValue ? "warning" : "success"
      );
    } catch (e: unknown) {
      // Revert on failure
      setData((prev) => ({ ...prev, kill_switch_active: !newValue }));
      toast(e instanceof Error ? e.message : "Failed to update kill switch", "error");
    }
  };

  if (loading) {
    return (
      <Surface>
        <SurfaceHeader>
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <Settings className="h-4 w-4 text-muted-foreground" />
              <SurfaceTitle>Risk Limits Configuration</SurfaceTitle>
            </div>
            <div className="app-skeleton h-7 w-16 rounded-lg" />
          </div>
        </SurfaceHeader>
        <SurfaceBody className="p-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="app-inset p-3 space-y-0">
              <div className="app-skeleton h-3 w-32 rounded-full mb-3" />
              {[0, 1, 2, 3].map((i) => <LimitRowSkeleton key={i} />)}
            </div>
            <div className="app-inset p-3 space-y-0">
              <div className="app-skeleton h-3 w-36 rounded-full mb-3" />
              {[0, 1, 2].map((i) => <LimitRowSkeleton key={i} />)}
              <div className="app-skeleton h-10 w-full rounded-lg mt-2" />
            </div>
          </div>
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
            <span
              className="text-[10px] font-medium text-emerald-400 transition-all duration-300"
              style={{
                opacity: saved ? 1 : 0,
                transform: saved ? "translateX(0)" : "translateX(4px)",
              }}
              aria-live="polite"
            >
              Saved
            </span>
            {error && (
              <Badge variant="danger" className="text-[9px] py-0.5">
                Error
              </Badge>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              aria-label="Save risk limits"
              className="app-button-primary text-xs px-3 py-1.5 rounded-lg disabled:opacity-60 disabled:cursor-not-allowed"
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
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Drawdown Thresholds
              </span>
            </div>
            <LimitRow
              id="reduce-threshold"
              label="Reduce Size"
              description="Cut position sizing at this drawdown"
              value={data.reduce_threshold}
              onChange={(v) => setData((p) => ({ ...p, reduce_threshold: v }))}
              suffix="%"
              min={-20}
              max={0}
            />
            <LimitRow
              id="halt-threshold"
              label="Halt New Trades"
              description="Stop opening new positions"
              value={data.halt_threshold}
              onChange={(v) => setData((p) => ({ ...p, halt_threshold: v }))}
              suffix="%"
              min={-30}
              max={0}
            />
            <LimitRow
              id="daily-kill-threshold"
              label="Daily Kill"
              description="Close all positions for the day"
              value={data.daily_kill_threshold}
              onChange={(v) => setData((p) => ({ ...p, daily_kill_threshold: v }))}
              suffix="%"
              min={-50}
              max={0}
            />
            <LimitRow
              id="weekly-kill-threshold"
              label="Weekly Kill"
              description="Halt all trading for the week"
              value={data.weekly_kill_threshold}
              onChange={(v) => setData((p) => ({ ...p, weekly_kill_threshold: v }))}
              suffix="%"
              min={-50}
              max={0}
            />
          </div>

          {/* Right Panel: Concentration & Safety */}
          <div className="app-inset p-3 space-y-0">
            <div className="flex items-center gap-2 pb-2 border-b border-border/40 mb-1">
              <ShieldAlert className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Concentration & Safety
              </span>
            </div>
            <LimitRow
              id="sector-cap"
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
              id="category-block"
              label="Category Block"
              description="Block strategies scoring below this"
              value={data.category_block_threshold}
              onChange={(v) => setData((p) => ({ ...p, category_block_threshold: v }))}
              suffix="/100"
              min={0}
              max={100}
              step={5}
            />
            <LimitRow
              id="max-position-size"
              label="Max Position Size"
              description="Maximum % of portfolio per position"
              value={data.max_position_size}
              onChange={(v) => setData((p) => ({ ...p, max_position_size: v }))}
              suffix="%"
              min={1}
              max={50}
              step={1}
            />

            {/* Kill Switch */}
            <div className="flex items-center justify-between gap-3 py-2.5 mt-1 border-t border-border/40">
              <div className="min-w-0">
                <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <span
                    className="transition-all duration-200"
                    style={{ color: data.kill_switch_active ? "#f87171" : "#34d399" }}
                  >
                    {data.kill_switch_active ? (
                      <ShieldAlert className="h-3.5 w-3.5" />
                    ) : (
                      <ShieldCheck className="h-3.5 w-3.5" />
                    )}
                  </span>
                  Kill Switch
                </div>
                <div className="text-[10px] text-muted-foreground mt-0.5 transition-all duration-200">
                  {data.kill_switch_active
                    ? "Trading halted — all bots stopped"
                    : "Trading active — bots running normally"}
                </div>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={data.kill_switch_active}
                aria-label={data.kill_switch_active ? "Disable kill switch" : "Enable kill switch"}
                onClick={toggleKillSwitch}
                className={[
                  "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent",
                  "transition-colors duration-200 ease-in-out",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  "active:scale-95",
                  data.kill_switch_active ? "bg-red-500" : "bg-emerald-500",
                ].join(" ")}
              >
                <span
                  className={[
                    "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0",
                    "transition-transform duration-200 ease-in-out",
                    data.kill_switch_active ? "translate-x-5" : "translate-x-0",
                  ].join(" ")}
                />
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-500/25 bg-red-500/8 px-3 py-2 text-xs text-red-300 animate-in fade-in slide-in-from-top-1 duration-200">
            <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
            {error}
          </div>
        )}
      </SurfaceBody>
    </Surface>
  );
}
