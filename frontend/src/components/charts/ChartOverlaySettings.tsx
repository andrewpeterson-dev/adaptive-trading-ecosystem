"use client";

import React, { useRef, useState, useEffect, useCallback } from "react";
import { Settings } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import type { HeatmapConfig } from "@/types/chart";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChartOverlaySettingsProps {
  heatmapConfig: HeatmapConfig;
  onHeatmapConfigChange: (config: HeatmapConfig) => void;
  aiSignalsEnabled: boolean;
  onAiSignalsEnabledChange: (enabled: boolean) => void;
  tradeMarkersEnabled: boolean;
  onTradeMarkersEnabledChange: (enabled: boolean) => void;
  indicatorsEnabled: boolean;
  onIndicatorsEnabledChange: (enabled: boolean) => void;
  theme: "dark" | "light";
}

// ---------------------------------------------------------------------------
// Slider sub-component (inline, no external dep)
// ---------------------------------------------------------------------------

function MiniSlider({
  value,
  min,
  max,
  step,
  label,
  displayValue,
  onChange,
  theme,
}: {
  value: number;
  min: number;
  max: number;
  step: number;
  label: string;
  displayValue: string;
  onChange: (v: number) => void;
  theme: "dark" | "light";
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-muted-foreground">{label}</span>
        <span className="text-[11px] font-mono tabular-nums text-foreground">{displayValue}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
        style={{
          background: theme === "dark"
            ? "linear-gradient(to right, #334155, #64748b)"
            : "linear-gradient(to right, #cbd5e1, #94a3b8)",
          accentColor: theme === "dark" ? "#3b82f6" : "#2563eb",
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toggle row
// ---------------------------------------------------------------------------

function ToggleRow({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className={`text-[11px] ${disabled ? "text-muted-foreground/50" : "text-muted-foreground"}`}>
        {label}
      </span>
      <Switch
        checked={checked}
        onClick={() => !disabled && onChange(!checked)}
        disabled={disabled}
        className={disabled ? "opacity-40 cursor-not-allowed" : ""}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChartOverlaySettings({
  heatmapConfig,
  onHeatmapConfigChange,
  aiSignalsEnabled,
  onAiSignalsEnabledChange,
  tradeMarkersEnabled,
  onTradeMarkersEnabledChange,
  indicatorsEnabled,
  onIndicatorsEnabledChange,
  theme,
}: ChartOverlaySettingsProps) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open]);

  const updateHeatmap = useCallback(
    (partial: Partial<HeatmapConfig>) => {
      onHeatmapConfigChange({ ...heatmapConfig, ...partial });
    },
    [heatmapConfig, onHeatmapConfigChange],
  );

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={() => setOpen((prev) => !prev)}
        className={`inline-flex items-center justify-center rounded-full p-2 transition-colors ${
          open
            ? "bg-foreground/10 text-foreground"
            : "text-muted-foreground/60 hover:text-muted-foreground hover:bg-foreground/5"
        }`}
        title="Chart overlay settings"
        type="button"
      >
        <Settings className="h-3.5 w-3.5" />
      </button>

      {open && (
        <div
          ref={panelRef}
          className="absolute right-0 top-full mt-2 z-50 w-[240px] rounded-2xl border p-4 shadow-lg"
          style={{
            backgroundColor: theme === "dark" ? "rgba(8, 17, 31, 0.96)" : "rgba(255, 255, 255, 0.98)",
            borderColor: theme === "dark" ? "rgba(51, 65, 85, 0.6)" : "rgba(203, 213, 225, 0.8)",
          }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-3">
            Chart Overlays
          </div>

          <div className="flex flex-col gap-3">
            <ToggleRow
              label="AI Signals"
              checked={aiSignalsEnabled}
              onChange={onAiSignalsEnabledChange}
            />
            <ToggleRow
              label="Heatmap"
              checked={heatmapConfig.enabled}
              onChange={(v) => updateHeatmap({ enabled: v })}
            />
            <ToggleRow
              label="Trade Markers"
              checked={tradeMarkersEnabled}
              onChange={onTradeMarkersEnabledChange}
            />
            <ToggleRow
              label="Indicators"
              checked={indicatorsEnabled}
              onChange={onIndicatorsEnabledChange}
            />

            {/* Heatmap sub-settings */}
            {heatmapConfig.enabled && (
              <div className="mt-1 pt-3 border-t border-border/40 flex flex-col gap-3">
                <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/70">
                  Heatmap Settings
                </div>

                <MiniSlider
                  label="Intensity"
                  value={heatmapConfig.intensity}
                  min={0.3}
                  max={1.0}
                  step={0.05}
                  displayValue={`${Math.round(heatmapConfig.intensity * 100)}%`}
                  onChange={(v) => updateHeatmap({ intensity: v })}
                  theme={theme}
                />

                <MiniSlider
                  label="Cluster threshold"
                  value={heatmapConfig.clusterThreshold}
                  min={1}
                  max={10}
                  step={1}
                  displayValue={`${heatmapConfig.clusterThreshold}`}
                  onChange={(v) => updateHeatmap({ clusterThreshold: v })}
                  theme={theme}
                />

                <ToggleRow
                  label="Buy heat colors"
                  checked={heatmapConfig.showBuyZones}
                  onChange={(v) => updateHeatmap({ showBuyZones: v })}
                />
                <ToggleRow
                  label="Sell heat colors"
                  checked={heatmapConfig.showSellZones}
                  onChange={(v) => updateHeatmap({ showSellZones: v })}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
