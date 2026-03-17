"use client";

import { useState } from "react";
import { useBuilderStore } from "@/stores/builder-store";
import { validateStrategy } from "@/lib/strategy-validation";
import { apiFetch } from "@/lib/api/client";
import { sendChatMessage } from "@/lib/cerberus-api";
import type { StrategyCondition } from "@/types/strategy";
import type { PageContext } from "@/types/cerberus";

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

  // -- Local UI state for save / deploy flows --
  const [saving, setSaving] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"saved" | "error" | null>(null);
  const [deployStatus, setDeployStatus] = useState<"deployed" | "error" | null>(null);

  // -------------------------------------------------------------------------
  // Save Draft
  // -------------------------------------------------------------------------

  const handleSave = async () => {
    setSaving(true);
    try {
      const s = useBuilderStore.getState();
      const payload = {
        name: s.name,
        description: s.description,
        action: s.action,
        condition_groups: s.conditionGroups,
        stop_loss_pct: s.stopLoss / 100,
        take_profit_pct: s.takeProfit / 100,
        position_size_pct: s.positionSize / 100,
        timeframe: s.timeframe,
        symbols: s.symbols,
        commission_pct: s.commissionPct / 100,
        slippage_pct: s.slippagePct / 100,
        trailing_stop_pct: s.trailingStopEnabled ? s.trailingStop / 100 : null,
        exit_after_bars: s.exitAfterBarsEnabled ? s.exitAfterBars : null,
        cooldown_bars: s.cooldownBars,
        max_trades_per_day: s.maxTradesPerDay,
        max_exposure_pct: s.maxExposurePct / 100,
        max_loss_pct: s.maxLossPct / 100,
        strategy_type: s.strategyType,
        source_prompt: s.sourcePrompt || null,
        ai_context: s.aiContext || null,
      };

      await apiFetch("/api/strategies/create", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setSaveStatus("saved");
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err) {
      setSaveStatus("error");
      console.error("Save failed:", err);
      throw err; // Re-throw so callers (e.g. handleDeploy) know the save failed
    } finally {
      setSaving(false);
    }
  };

  // -------------------------------------------------------------------------
  // Deploy Bot
  // -------------------------------------------------------------------------

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      // Step 1: Save the strategy first — will throw on failure
      await handleSave();

      // Step 2: Ask Cerberus to deploy as a bot
      const s = useBuilderStore.getState();
      const config = {
        name: s.name,
        action: s.action,
        timeframe: s.timeframe,
        symbols: s.symbols,
        conditions: s.conditionGroups.flatMap((g) => g.conditions),
        stop_loss_pct: s.stopLoss / 100,
        take_profit_pct: s.takeProfit / 100,
        position_size_pct: s.positionSize / 100,
      };

      const pageContext: PageContext = {
        currentPage: "strategy-builder",
        route: "/strategy-builder",
        visibleComponents: ["StrategyPreview"],
        focusedComponent: "StrategyPreview",
        selectedSymbol: null,
        selectedAccountId: null,
        selectedBotId: null,
        componentState: {},
      };

      await sendChatMessage({
        mode: "strategy",
        message: `Deploy the strategy "${s.name}" as a live trading bot. Use createBot with this config: ${JSON.stringify(config)}`,
        pageContext,
      });

      setDeployStatus("deployed");
      setTimeout(() => setDeployStatus(null), 5000);
    } catch (err) {
      setDeployStatus("error");
      console.error("Deploy failed:", err);
    } finally {
      setDeploying(false);
    }
  };

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

      {/* ---- Status feedback ---- */}
      {saveStatus === "saved" && (
        <div className="app-card p-2 border-l-4 border-emerald-500 text-sm text-emerald-400">
          Strategy saved successfully.
        </div>
      )}
      {saveStatus === "error" && (
        <div className="app-card p-2 border-l-4 border-red-500 text-sm text-red-400">
          Failed to save strategy. Check console for details.
        </div>
      )}
      {deployStatus === "deployed" && (
        <div className="app-card p-2 border-l-4 border-emerald-500 text-sm text-emerald-400">
          Bot deployment initiated. Check the Bots tab for status.
        </div>
      )}
      {deployStatus === "error" && (
        <div className="app-card p-2 border-l-4 border-red-500 text-sm text-red-400">
          Deployment failed. Check console for details.
        </div>
      )}

      {/* ---- Action buttons ---- */}
      <div className="mt-auto space-y-2 pt-4">
        <button
          className="app-button-primary w-full"
          disabled={!canSave || deploying}
          onClick={handleDeploy}
        >
          {deploying ? "Deploying..." : "Deploy Bot"}
          {!canSave && !deploying && issues.length > 0 && (
            <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-white/20 text-xs font-bold">
              {issues.length}
            </span>
          )}
        </button>

        <button
          className="app-button-secondary w-full"
          disabled={!canSave || saving}
          onClick={handleSave}
        >
          {saving ? "Saving..." : "Save Draft"}
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
