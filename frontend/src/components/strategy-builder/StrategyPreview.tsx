"use client";

import { useState } from "react";
import { useBuilderStore } from "@/stores/builder-store";
import { validateStrategy } from "@/lib/strategy-validation";
import { apiFetch } from "@/lib/api/client";
import { sendChatMessage } from "@/lib/cerberus-api";
import type { StrategyCondition } from "@/types/strategy";
import type { PageContext } from "@/types/cerberus";
import { Eye, Code, AlertTriangle, CheckCircle2, XCircle, Rocket, Save, Shield } from "lucide-react";

interface StrategyPreviewProps {
  activeMode: "ai" | "manual" | "template";
  onModeSwitch: (mode: "ai" | "manual" | "template") => void;
}

function formatCondition(c: StrategyCondition): string {
  const name = c.indicator.toUpperCase();
  const paramValues = Object.values(c.params ?? {});
  const paramStr = paramValues.length > 0 ? `(${paramValues.join(", ")})` : "";
  const op = c.operator === "crosses_above" ? "crosses above"
    : c.operator === "crosses_below" ? "crosses below"
    : c.operator;
  return `${name}${paramStr} ${op} ${c.value}`;
}

export default function StrategyPreview({ activeMode, onModeSwitch }: StrategyPreviewProps) {
  const state = useBuilderStore();
  const [viewMode, setViewMode] = useState<"visual" | "json">("visual");
  const [saving, setSaving] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"saved" | "error" | null>(null);
  const [deployStatus, setDeployStatus] = useState<"deployed" | "error" | null>(null);

  const {
    name, description, action, timeframe, symbols,
    conditionGroups, exitConditionGroups,
    stopLoss, takeProfit, positionSize,
    trailingStopEnabled, trailingStop,
    strategyType, sourcePrompt,
  } = state;

  const { canSave, issues } = validateStrategy(state);

  // Build the JSON schema output
  const schemaOutput = {
    name: name || "Untitled Strategy",
    description,
    type: strategyType,
    action,
    timeframe,
    symbols,
    entry_conditions: conditionGroups.map(g => ({
      group_id: g.id,
      joiner: g.joiner || "AND",
      conditions: g.conditions.filter(c => c.indicator).map(c => ({
        indicator: c.indicator,
        params: c.params,
        operator: c.operator,
        value: c.value,
        ...(c.compare_to ? { compare_to: c.compare_to } : {}),
      })),
    })),
    exit_conditions: exitConditionGroups.map(g => ({
      group_id: g.id,
      joiner: g.joiner || "AND",
      conditions: g.conditions.filter(c => c.indicator).map(c => ({
        indicator: c.indicator,
        params: c.params,
        operator: c.operator,
        value: c.value,
      })),
    })),
    risk_management: {
      stop_loss_pct: stopLoss,
      take_profit_pct: takeProfit,
      position_size_pct: positionSize,
      trailing_stop: trailingStopEnabled ? trailingStop : null,
    },
  };

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
      throw err;
    } finally {
      setSaving(false);
    }
  };

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      await handleSave();
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

  return (
    <div className="flex flex-col h-full">
      {/* Header with view toggle */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h3 className="text-sm font-semibold text-foreground">Strategy Preview</h3>
        <div className="app-segmented">
          <button
            className={`app-segment text-xs flex items-center gap-1.5 ${viewMode === "visual" ? "app-toggle-active" : ""}`}
            onClick={() => setViewMode("visual")}
          >
            <Eye className="w-3 h-3" />
            Visual
          </button>
          <button
            className={`app-segment text-xs flex items-center gap-1.5 ${viewMode === "json" ? "app-toggle-active" : ""}`}
            onClick={() => setViewMode("json")}
          >
            <Code className="w-3 h-3" />
            JSON
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {viewMode === "json" ? (
          /* JSON View */
          <div className="app-card p-4">
            <pre className="text-xs font-mono text-slate-300 whitespace-pre-wrap overflow-x-auto leading-relaxed">
              {JSON.stringify(schemaOutput, null, 2)}
            </pre>
          </div>
        ) : (
          /* Visual View */
          <>
            {/* Header card */}
            <div className="app-card p-4 space-y-2">
              <h2 className="text-base font-bold text-foreground">
                {name.trim() || "Untitled Strategy"}
              </h2>
              {description && (
                <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
              )}
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                  action === "BUY" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                }`}>
                  {action}
                </span>
                <span className="app-pill text-[10px]">{timeframe}</span>
                {symbols.map((s) => (
                  <span key={s} className="app-pill text-[10px] font-mono">{s}</span>
                ))}
              </div>
            </div>

            {/* Entry conditions */}
            <div className="app-card p-4 border-l-2 border-emerald-500/60">
              <p className="text-xs font-semibold text-emerald-400 mb-2 flex items-center gap-1.5">
                <TrendingUpIcon /> Entry Conditions
              </p>
              {conditionGroups.length === 0 || conditionGroups.every((g) => g.conditions.length === 0) ? (
                <p className="text-xs text-muted-foreground">No entry conditions defined</p>
              ) : (
                <div className="space-y-1.5 text-xs">
                  {conditionGroups.map((group, gi) => (
                    <div key={group.id}>
                      {gi > 0 && <span className="block text-amber-500 font-bold text-[10px] my-1 uppercase">or</span>}
                      {group.conditions.filter(c => c.indicator).map((cond, ci) => (
                        <div key={cond.id} className="flex items-center gap-1.5 text-slate-300">
                          {ci > 0 && <span className="text-emerald-500 font-bold text-[10px] uppercase">and</span>}
                          <span className="font-mono">{formatCondition(cond)}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Exit conditions */}
            <div className="app-card p-4 border-l-2 border-red-500/60">
              <p className="text-xs font-semibold text-red-400 mb-2 flex items-center gap-1.5">
                <TrendingDownIcon /> Exit Conditions
              </p>
              {exitConditionGroups.length === 0 || exitConditionGroups.every((g) => g.conditions.length === 0) ? (
                <p className="text-xs text-muted-foreground">Using stop loss / take profit only</p>
              ) : (
                <div className="space-y-1.5 text-xs">
                  {exitConditionGroups.map((group, gi) => (
                    <div key={group.id}>
                      {gi > 0 && <span className="block text-amber-500 font-bold text-[10px] my-1 uppercase">or</span>}
                      {group.conditions.filter(c => c.indicator).map((cond, ci) => (
                        <div key={cond.id} className="flex items-center gap-1.5 text-slate-300">
                          {ci > 0 && <span className="text-emerald-500 font-bold text-[10px] uppercase">and</span>}
                          <span className="font-mono">{formatCondition(cond)}</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Risk controls */}
            <div className="app-card p-4 border-l-2 border-amber-500/60">
              <p className="text-xs font-semibold text-amber-400 mb-2 flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5" /> Risk Controls
              </p>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="text-muted-foreground">Stop Loss</p>
                  <p className="text-foreground font-semibold font-mono">{stopLoss}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Take Profit</p>
                  <p className="text-foreground font-semibold font-mono">{takeProfit}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Position Size</p>
                  <p className="text-foreground font-semibold font-mono">{positionSize}%</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Trailing Stop</p>
                  <p className="text-foreground font-semibold font-mono">{trailingStopEnabled ? `${trailingStop}%` : "Off"}</p>
                </div>
              </div>
            </div>

            {/* Validation */}
            {issues.length > 0 && (
              <div className="app-card p-3 border-l-2 border-orange-500/60">
                <p className="text-xs font-semibold text-orange-400 mb-1.5 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Issues ({issues.length})
                </p>
                <ul className="text-[11px] text-orange-300/80 space-y-0.5">
                  {issues.map((issue) => (
                    <li key={issue} className="flex items-start gap-1.5">
                      <span className="text-orange-500 mt-0.5">&#8226;</span>
                      {issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}

        {/* Status feedback */}
        {saveStatus === "saved" && (
          <div className="flex items-center gap-2 app-card p-3 border-l-2 border-emerald-500/60 text-xs text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" /> Strategy saved successfully.
          </div>
        )}
        {saveStatus === "error" && (
          <div className="flex items-center gap-2 app-card p-3 border-l-2 border-red-500/60 text-xs text-red-400">
            <XCircle className="w-3.5 h-3.5" /> Failed to save. Check console.
          </div>
        )}
        {deployStatus === "deployed" && (
          <div className="flex items-center gap-2 app-card p-3 border-l-2 border-emerald-500/60 text-xs text-emerald-400">
            <Rocket className="w-3.5 h-3.5" /> Bot deployment initiated.
          </div>
        )}
        {deployStatus === "error" && (
          <div className="flex items-center gap-2 app-card p-3 border-l-2 border-red-500/60 text-xs text-red-400">
            <XCircle className="w-3.5 h-3.5" /> Deployment failed. Check console.
          </div>
        )}
      </div>

      {/* Action buttons -- sticky bottom */}
      <div className="border-t border-border p-4 space-y-2 bg-card/50">
        <button
          className="app-button-primary w-full flex items-center justify-center gap-2"
          disabled={!canSave || deploying}
          onClick={handleDeploy}
        >
          <Rocket className="w-4 h-4" />
          {deploying ? "Deploying..." : "Deploy Bot"}
        </button>
        <button
          className="app-button-secondary w-full flex items-center justify-center gap-2"
          disabled={!canSave || saving}
          onClick={handleSave}
        >
          <Save className="w-4 h-4" />
          {saving ? "Saving..." : "Save Draft"}
        </button>
        <button
          className="app-button-ghost w-full text-xs"
          onClick={() => onModeSwitch(activeMode === "ai" ? "manual" : "ai")}
        >
          {activeMode === "ai" ? "Switch to Manual Editor" : "Switch to AI Builder"}
        </button>
      </div>
    </div>
  );
}

// Small inline SVG icons to avoid import bloat
function TrendingUpIcon() {
  return (
    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
      <polyline points="16 7 22 7 22 13" />
    </svg>
  );
}

function TrendingDownIcon() {
  return (
    <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 17 13.5 8.5 8.5 13.5 2 7" />
      <polyline points="16 17 22 17 22 11" />
    </svg>
  );
}
