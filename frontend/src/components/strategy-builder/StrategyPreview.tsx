"use client";

import { useBuilderStore } from "@/stores/builder-store";
import { validateStrategy } from "@/lib/strategy-validation";
import type { StrategyCondition } from "@/types/strategy";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StrategyPreviewProps {
  activeMode: "ai" | "manual" | "template";
  onModeSwitch: (mode: "ai" | "manual" | "template") => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Render a condition as human-readable text, e.g. "RSI(14) < 30" */
function formatCondition(c: StrategyCondition): string {
  const name = c.indicator.toUpperCase();
  const paramValues = Object.values(c.params ?? {});
  const paramStr = paramValues.length > 0 ? `(${paramValues.join(", ")})` : "";
  const op = c.operator === "crosses_above"
    ? "crosses above"
    : c.operator === "crosses_below"
      ? "crosses below"
      : c.operator;
  return `${name}${paramStr} ${op} ${c.value}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function StrategyPreview({ activeMode, onModeSwitch }: StrategyPreviewProps) {
  const state = useBuilderStore();

  const {
    name,
    action,
    timeframe,
    symbols,
    conditionGroups,
    exitConditionGroups,
    stopLoss,
    takeProfit,
    positionSize,
    trailingStopEnabled,
    trailingStop,
  } = state;

  const { canSave, issues } = validateStrategy(state);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full overflow-y-auto gap-4 p-4">
      {/* ---- Header card ---- */}
      <div className="app-card p-4 space-y-3">
        <h2 className="text-lg font-semibold text-slate-100">
          {name.trim() || "Untitled Strategy"}
        </h2>

        <div className="flex flex-wrap items-center gap-2">
          {/* Action badge */}
          <span
            className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${
              action === "BUY"
                ? "bg-emerald-500/20 text-emerald-400"
                : "bg-red-500/20 text-red-400"
            }`}
          >
            {action}
          </span>

          {/* Timeframe pill */}
          <span className="app-pill">{timeframe}</span>

          {/* Symbol pills */}
          {symbols.map((s) => (
            <span key={s} className="app-pill">
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* ---- Entry conditions card ---- */}
      <div className="app-card p-4 border-l-4 border-blue-500">
        <p className="app-label mb-2">Entry Conditions</p>

        {conditionGroups.length === 0 ||
        conditionGroups.every((g) => g.conditions.length === 0) ? (
          <p className="text-sm text-slate-500">No entry conditions defined</p>
        ) : (
          <div className="space-y-2 text-sm text-slate-300">
            {conditionGroups.map((group, gi) => (
              <div key={group.id}>
                {gi > 0 && (
                  <span className="block text-amber-500 font-semibold text-xs my-1">
                    OR
                  </span>
                )}
                {group.conditions.map((cond, ci) => (
                  <div key={cond.id} className="flex items-center gap-1">
                    {ci > 0 && (
                      <span className="text-emerald-500 font-semibold text-xs mr-1">
                        AND
                      </span>
                    )}
                    <span>{formatCondition(cond)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---- Exit conditions card ---- */}
      <div className="app-card p-4 border-l-4 border-red-500">
        <p className="app-label mb-2">Exit Conditions</p>

        {exitConditionGroups.length === 0 ||
        exitConditionGroups.every((g) => g.conditions.length === 0) ? (
          <p className="text-sm text-slate-500">No exit conditions defined</p>
        ) : (
          <div className="space-y-2 text-sm text-slate-300">
            {exitConditionGroups.map((group, gi) => (
              <div key={group.id}>
                {gi > 0 && (
                  <span className="block text-amber-500 font-semibold text-xs my-1">
                    OR
                  </span>
                )}
                {group.conditions.map((cond, ci) => (
                  <div key={cond.id} className="flex items-center gap-1">
                    {ci > 0 && (
                      <span className="text-emerald-500 font-semibold text-xs mr-1">
                        AND
                      </span>
                    )}
                    <span>{formatCondition(cond)}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        <p className="text-xs text-slate-500 mt-3">
          Stop Loss: {stopLoss}% &middot; Take Profit: {takeProfit}%
        </p>
      </div>

      {/* ---- Risk controls card ---- */}
      <div className="app-card p-4 border-l-4 border-amber-500">
        <p className="app-label mb-2">Risk Controls</p>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p className="text-slate-500 text-xs">Stop Loss</p>
            <p className="text-slate-200 font-medium">{stopLoss}%</p>
          </div>
          <div>
            <p className="text-slate-500 text-xs">Take Profit</p>
            <p className="text-slate-200 font-medium">{takeProfit}%</p>
          </div>
          <div>
            <p className="text-slate-500 text-xs">Position Size</p>
            <p className="text-slate-200 font-medium">{positionSize}%</p>
          </div>
          <div>
            <p className="text-slate-500 text-xs">Trailing Stop</p>
            <p className="text-slate-200 font-medium">
              {trailingStopEnabled ? `${trailingStop}%` : "Off"}
            </p>
          </div>
        </div>
      </div>

      {/* ---- Validation issues ---- */}
      {issues.length > 0 && (
        <div className="app-card p-3 border-l-4 border-orange-500 text-sm text-orange-300 space-y-1">
          <p className="font-semibold flex items-center gap-2">
            Issues
            <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-orange-500/20 text-xs font-bold">
              {issues.length}
            </span>
          </p>
          <ul className="list-disc list-inside text-xs space-y-0.5">
            {issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </div>
      )}

      {/* ---- Action buttons ---- */}
      <div className="mt-auto space-y-2 pt-4">
        <button
          className="app-button-primary w-full"
          disabled={!canSave}
          onClick={() => console.log("[StrategyPreview] Deploy Bot clicked")}
        >
          Deploy Bot
          {!canSave && issues.length > 0 && (
            <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-white/20 text-xs font-bold">
              {issues.length}
            </span>
          )}
        </button>

        <button
          className="app-button-secondary w-full"
          disabled={!canSave}
          onClick={() => console.log("[StrategyPreview] Save Draft clicked")}
        >
          Save Draft
        </button>

        <button
          className="app-button-ghost w-full"
          onClick={() =>
            onModeSwitch(activeMode === "ai" ? "manual" : "ai")
          }
        >
          {activeMode === "ai" ? "Edit in Manual" : "Edit with AI"}
        </button>
      </div>
    </div>
  );
}
