"use client";

import React, { useState, useCallback, useEffect } from "react";
import { Plus, Play, Save, RotateCcw, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api/client";
import { ConditionGroup as ConditionGroupComponent } from "./ConditionGroup";
import { AccordionSection } from "./AccordionSection";
import { DiagnosticPanel } from "./DiagnosticPanel";
import { ExplainerPanel } from "./ExplainerPanel";
import { IndicatorChart } from "@/components/charts/IndicatorChart";
import type {
  ConditionGroup,
  StrategyCondition,
  Strategy,
  StrategyRecord,
  DiagnosticReport,
  StrategyExplanation,
  Action,
} from "@/types/strategy";

// ── Helpers ────────────────────────────────────────────────────────────────

function genId(): string {
  return `id_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function emptyCondition(): StrategyCondition {
  return { id: genId(), indicator: "", operator: "<", value: 30, params: {}, action: "BUY" };
}

function emptyGroup(index = 0): ConditionGroup {
  return {
    id: genId(),
    label: `Group ${String.fromCharCode(65 + index)}`,
    conditions: [emptyCondition()],
  };
}

function buildLogicString(groups: ConditionGroup[], action: Action): string {
  const groupParts = groups
    .map((g) => {
      const condParts = g.conditions
        .filter((c) => c.indicator)
        .map((c) => {
          const paramStr = Object.values(c.params).join(",");
          const ind = c.indicator.toUpperCase().replace(/_/g, " ");
          const indFmt = paramStr ? `${ind}(${paramStr})` : ind;
          return `${indFmt} ${c.operator} ${c.value}`;
        });
      if (condParts.length === 0) return null;
      return condParts.length === 1 ? condParts[0] : `(${condParts.join(" AND ")})`;
    })
    .filter(Boolean);
  if (groupParts.length === 0) return "";
  return `IF ${groupParts.join(" OR ")} THEN ${action}`;
}

// ── Props ──────────────────────────────────────────────────────────────────

interface StrategyBuilderProps {
  initialStrategy?: StrategyRecord;
  mode?: "create" | "edit";
}

// ── Component ──────────────────────────────────────────────────────────────

export function StrategyBuilder({ initialStrategy, mode = "create" }: StrategyBuilderProps) {
  const router = useRouter();

  // Core identity
  const [name, setName] = useState("My Strategy");
  const [description, setDescription] = useState("");
  const [action, setAction] = useState<Action>("BUY");
  const [timeframe, setTimeframe] = useState("1D");

  // Condition groups (primary state — replaces flat conditions[])
  const [conditionGroups, setConditionGroups] = useState<ConditionGroup[]>([emptyGroup(0)]);

  // Exit conditions
  const [stopLoss, setStopLoss] = useState(2);
  const [takeProfit, setTakeProfit] = useState(5);
  const [positionSize, setPositionSize] = useState(10);
  const [trailingStopEnabled, setTrailingStopEnabled] = useState(false);
  const [trailingStop, setTrailingStop] = useState(1.5);
  const [exitAfterBarsEnabled, setExitAfterBarsEnabled] = useState(false);
  const [exitAfterBars, setExitAfterBars] = useState(10);

  // Universe
  const [symbols, setSymbols] = useState<string[]>(["SPY"]);
  const [symbolInput, setSymbolInput] = useState("");

  // Execution
  const [commissionPct, setCommissionPct] = useState(0.1);  // display as %
  const [slippagePct, setSlippagePct] = useState(0.05);

  // Risk
  const [cooldownBars, setCooldownBars] = useState(0);
  const [maxTradesPerDay, setMaxTradesPerDay] = useState(0);
  const [maxExposurePct, setMaxExposurePct] = useState(100);
  const [maxLossPct, setMaxLossPct] = useState(0);

  // UI state
  const [diagnostics, setDiagnostics] = useState<DiagnosticReport | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [explanation, setExplanation] = useState<StrategyExplanation | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [indicatorPreviews, setIndicatorPreviews] = useState<
    Record<string, { values?: number[]; components?: Record<string, number[]> }>
  >({});

  // ── Populate from initialStrategy (edit mode) ──────────────────────────

  useEffect(() => {
    if (!initialStrategy) return;
    setName(initialStrategy.name);
    setDescription(initialStrategy.description || "");
    setAction(initialStrategy.action as Action);
    setStopLoss((initialStrategy.stop_loss_pct || 0.02) * 100);
    setTakeProfit((initialStrategy.take_profit_pct || 0.05) * 100);
    setPositionSize((initialStrategy.position_size_pct || 0.1) * 100);
    setTimeframe(initialStrategy.timeframe || "1D");
    setSymbols(initialStrategy.symbols?.length ? initialStrategy.symbols : ["SPY"]);
    setCommissionPct((initialStrategy.commission_pct ?? 0.001) * 100);
    setSlippagePct((initialStrategy.slippage_pct ?? 0.0005) * 100);
    if (initialStrategy.trailing_stop_pct != null) {
      setTrailingStopEnabled(true);
      setTrailingStop(initialStrategy.trailing_stop_pct * 100);
    }
    if (initialStrategy.exit_after_bars != null) {
      setExitAfterBarsEnabled(true);
      setExitAfterBars(initialStrategy.exit_after_bars);
    }
    setCooldownBars(initialStrategy.cooldown_bars ?? 0);
    setMaxTradesPerDay(initialStrategy.max_trades_per_day ?? 0);
    setMaxExposurePct((initialStrategy.max_exposure_pct ?? 1.0) * 100);
    setMaxLossPct((initialStrategy.max_loss_pct ?? 0) * 100);

    // Prefer condition_groups; fall back to wrapping flat conditions in one group
    if (initialStrategy.condition_groups?.length) {
      setConditionGroups(
        initialStrategy.condition_groups.map((g, gi) => ({
          id: genId(),
          label: g.label ?? `Group ${String.fromCharCode(65 + gi)}`,
          conditions: g.conditions.map((c) => ({
            id: genId(),
            indicator: c.indicator,
            operator: c.operator as StrategyCondition["operator"],
            value: c.value,
            compare_to: c.compare_to,
            params: c.params || {},
            action: (c.action as Action) || (initialStrategy.action as Action),
          })),
        }))
      );
    } else if (initialStrategy.conditions?.length) {
      setConditionGroups([
        {
          id: genId(),
          label: "Group A",
          conditions: initialStrategy.conditions.map((c) => ({
            id: genId(),
            indicator: c.indicator,
            operator: c.operator as StrategyCondition["operator"],
            value: c.value,
            compare_to: c.compare_to,
            params: c.params || {},
            action: (c.action as Action) || (initialStrategy.action as Action),
          })),
        },
      ]);
    }
    if (initialStrategy.diagnostics) {
      setDiagnostics(initialStrategy.diagnostics as DiagnosticReport);
    }
  }, [initialStrategy]);

  // ── Group / condition handlers ─────────────────────────────────────────

  const addGroup = useCallback(() => {
    setConditionGroups((prev) => [...prev, emptyGroup(prev.length)]);
  }, []);

  const removeGroup = useCallback((groupIndex: number) => {
    setConditionGroups((prev) => prev.filter((_, i) => i !== groupIndex));
  }, []);

  const addCondition = useCallback((groupIndex: number) => {
    setConditionGroups((prev) =>
      prev.map((g, gi) =>
        gi === groupIndex
          ? { ...g, conditions: [...g.conditions, emptyCondition()] }
          : g
      )
    );
  }, []);

  const removeCondition = useCallback((groupIndex: number, condIndex: number) => {
    setConditionGroups((prev) =>
      prev
        .map((g, gi) => {
          if (gi !== groupIndex) return g;
          const newConds = g.conditions.filter((_, ci) => ci !== condIndex);
          return { ...g, conditions: newConds };
        })
        .filter((g) => g.conditions.length > 0) // auto-remove empty groups
    );
  }, []);

  const updateCondition = useCallback(
    (groupIndex: number, condIndex: number, updated: Partial<StrategyCondition>) => {
      setConditionGroups((prev) =>
        prev.map((g, gi) =>
          gi === groupIndex
            ? {
                ...g,
                conditions: g.conditions.map((c, ci) =>
                  ci === condIndex ? { ...c, ...updated } : c
                ),
              }
            : g
        )
      );
    },
    []
  );

  const resetBuilder = useCallback(() => {
    setConditionGroups([emptyGroup(0)]);
    setDiagnostics(null);
    setExplanation(null);
    setName("My Strategy");
    setDescription("");
    setSaveStatus("idle");
    setIndicatorPreviews({});
    setSymbols(["SPY"]);
    setTrailingStopEnabled(false);
    setExitAfterBarsEnabled(false);
  }, []);

  // ── Symbol tag input ────────────────────────────────────────────────────

  const addSymbol = useCallback((raw: string) => {
    const sym = raw.trim().toUpperCase().replace(/[^A-Z]/g, "");
    if (sym && !symbols.includes(sym)) setSymbols((prev) => [...prev, sym]);
    setSymbolInput("");
  }, [symbols]);

  // ── All valid (filled) conditions across all groups ────────────────────

  const allValidConditions = conditionGroups
    .flatMap((g) => g.conditions)
    .filter((c) => c.indicator);

  // ── Auto-diagnostics (debounced, uses apiFetch for auth) ───────────────

  const conditionKey = conditionGroups
    .flatMap((g) => g.conditions)
    .map((c) => `${c.indicator}:${c.operator}:${c.value}:${JSON.stringify(c.params)}`)
    .join("|");

  useEffect(() => {
    if (allValidConditions.length === 0) {
      setDiagnostics(null);
      return;
    }
    const timeout = setTimeout(async () => {
      setDiagLoading(true);
      try {
        const params: Record<string, Record<string, number>> = {};
        for (const c of allValidConditions) params[c.indicator] = c.params;
        const data = await apiFetch<DiagnosticReport>("/api/strategies/diagnose", {
          method: "POST",
          body: JSON.stringify({
            conditions: allValidConditions.map((c) => ({
              indicator: c.indicator,
              operator: c.operator,
              value: c.value,
              params: c.params,
              action: c.action,
            })),
            parameters: params,
          }),
        });
        setDiagnostics(data);
      } catch {
        // network error — silently ignore
      } finally {
        setDiagLoading(false);
      }
    }, 500);
    return () => clearTimeout(timeout);
  }, [conditionKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Indicator previews (debounced, uses apiFetch for auth) ────────────

  useEffect(() => {
    if (allValidConditions.length === 0) {
      setIndicatorPreviews({});
      return;
    }
    const timeout = setTimeout(async () => {
      const previews: typeof indicatorPreviews = {};
      await Promise.all(
        allValidConditions.map(async (c) => {
          try {
            const data = await apiFetch<{
              values?: number[];
              components?: Record<string, number[]>;
            }>("/api/strategies/compute-indicator", {
              method: "POST",
              body: JSON.stringify({ indicator: c.indicator, params: c.params }),
            });
            previews[c.indicator] = data;
          } catch {
            // ignore
          }
        })
      );
      setIndicatorPreviews(previews);
    }, 800);
    return () => clearTimeout(timeout);
  }, [conditionKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── AI Explainer ────────────────────────────────────────────────────────

  const runExplainer = async () => {
    const logic = buildLogicString(conditionGroups, action);
    if (!logic) return;
    setExplainLoading(true);
    try {
      const data = await apiFetch<StrategyExplanation>("/api/explain/strategy", {
        method: "POST",
        body: JSON.stringify({ strategy_logic: logic }),
      });
      setExplanation(data);
    } catch {
      // ignore
    } finally {
      setExplainLoading(false);
    }
  };

  // ── Save / Update ────────────────────────────────────────────────────────

  const saveStrategy = async () => {
    setSaveStatus("saving");
    const payload: Strategy = {
      name,
      description,
      condition_groups: conditionGroups,
      conditions: allValidConditions,   // flat array kept for diagnostics on backend
      action,
      stop_loss_pct: stopLoss / 100,
      take_profit_pct: takeProfit / 100,
      position_size_pct: positionSize / 100,
      timeframe,
      symbols,
      commission_pct: commissionPct / 100,
      slippage_pct: slippagePct / 100,
      trailing_stop_pct: trailingStopEnabled ? trailingStop / 100 : null,
      exit_after_bars: exitAfterBarsEnabled ? exitAfterBars : null,
      cooldown_bars: cooldownBars,
      max_trades_per_day: maxTradesPerDay,
      max_exposure_pct: maxExposurePct / 100,
      max_loss_pct: maxLossPct / 100,
    };

    try {
      if (mode === "edit" && initialStrategy) {
        await apiFetch(`/api/strategies/${initialStrategy.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        const created = await apiFetch<{ id: number }>("/api/strategies/create", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        // In create mode, redirect to edit after save so Backtest button becomes available
        setSaveStatus("saved");
        setTimeout(() => router.push(`/edit/${created.id}`), 1200);
        return;
      }
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch {
      setSaveStatus("error");
    }
  };

  // ── Derived state ────────────────────────────────────────────────────────

  const logicString = buildLogicString(conditionGroups, action);

  const getCategory = (indicator: string) => {
    const cats: Record<string, string> = {
      rsi: "Momentum", stochastic: "Momentum", macd: "Momentum",
      sma: "Trend", ema: "Trend",
      bollinger_bands: "Volatility", atr: "Volatility",
      vwap: "Volume", obv: "Volume",
    };
    return cats[indicator] || "Momentum";
  };

  const getThresholds = (indicator: string) => {
    const t: Record<string, { overbought?: number; oversold?: number }> = {
      rsi: { overbought: 70, oversold: 30 },
      stochastic: { overbought: 80, oversold: 20 },
    };
    return t[indicator];
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-semibold">
            {mode === "edit" ? "Edit Strategy" : "Strategy Builder"}
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {mode === "edit"
              ? `Editing strategy #${initialStrategy?.id}`
              : "Define entry conditions with real-time diagnostics"}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={resetBuilder}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
          <button
            type="button"
            onClick={runExplainer}
            disabled={allValidConditions.length === 0 || explainLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-primary border border-primary/20 hover:bg-primary/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Zap className="h-3.5 w-3.5" />
            {explainLoading ? "Analyzing…" : "Analyze"}
          </button>
          {mode === "edit" && initialStrategy && (
            <button
              onClick={() => router.push(`/backtest/${initialStrategy.id}`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-amber-400 border border-amber-400/20 hover:bg-amber-400/10 transition-colors"
            >
              <Play className="h-3.5 w-3.5" />
              Backtest
            </button>
          )}
          <button
            type="button"
            onClick={saveStrategy}
            disabled={allValidConditions.length === 0 || saveStatus === "saving"}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Save className="h-3.5 w-3.5" />
            {saveStatus === "saving"
              ? "Saving..."
              : saveStatus === "saved"
                ? "Saved ✓"
                : mode === "edit"
                  ? "Update Strategy"
                  : "Save"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Builder */}
        <div className="lg:col-span-2 space-y-4">
          {/* Name & description */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Strategy Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description..."
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
            </div>
          </div>

          {/* Action + timeframe + position size */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Action
              </label>
              <select
                value={action}
                onChange={(e) => setAction(e.target.value as Action)}
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-ring/40"
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Timeframe
              </label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40"
              >
                {["1m", "5m", "15m", "1H", "4H", "1D", "1W"].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Position %
              </label>
              <input
                type="number"
                value={positionSize}
                onChange={(e) => setPositionSize(parseFloat(e.target.value) || 0)}
                min={1} max={100} step={1}
                className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
            </div>
          </div>

          {/* Condition Groups */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Entry Conditions
              </h3>
              <span className="text-xs text-muted-foreground">
                {allValidConditions.length} active
              </span>
            </div>

            {conditionGroups.map((group, gi) => (
              <React.Fragment key={group.id}>
                <ConditionGroupComponent
                  group={group}
                  groupIndex={gi}
                  totalGroups={conditionGroups.length}
                  onAddCondition={addCondition}
                  onRemoveCondition={removeCondition}
                  onUpdateCondition={updateCondition}
                  onRemoveGroup={removeGroup}
                />
                {gi < conditionGroups.length - 1 && (
                  <div className="flex items-center justify-center">
                    <span className="text-[11px] font-bold px-3 py-1 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/20 uppercase tracking-widest">
                      OR
                    </span>
                  </div>
                )}
              </React.Fragment>
            ))}

            <button
              onClick={addGroup}
              className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed border-border/50 text-sm text-muted-foreground hover:text-foreground hover:border-amber-400/30 hover:bg-amber-400/5 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              Add OR Group
            </button>
          </div>

          {/* Logic preview */}
          {logicString && (
            <div className="rounded-lg border border-border/50 bg-muted/20 p-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
                Strategy Logic
              </div>
              <code className="text-sm font-mono text-primary break-all">{logicString}</code>
            </div>
          )}

          {/* Indicator previews */}
          {allValidConditions.length > 0 && Object.keys(indicatorPreviews).length > 0 && (
            <div className="space-y-2">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Indicator Previews
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {allValidConditions.map((c) => {
                  const preview = indicatorPreviews[c.indicator];
                  if (!preview) return null;
                  const category = getCategory(c.indicator);
                  const thresholds = getThresholds(c.indicator);
                  if (preview.components)
                    return (
                      <IndicatorChart key={c.id} data={[]} label={c.indicator.toUpperCase()}
                        category={category} thresholds={thresholds} multiLine={preview.components} />
                    );
                  if (preview.values)
                    return (
                      <IndicatorChart key={c.id} data={preview.values} label={c.indicator.toUpperCase()}
                        category={category} thresholds={thresholds} />
                    );
                  return null;
                })}
              </div>
            </div>
          )}

          {/* ── Accordions ──────────────────────────────────────────────── */}

          {/* Exit Conditions */}
          <AccordionSection title="Exit Conditions" defaultOpen>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Stop Loss %
                </label>
                <input type="number" value={stopLoss}
                  onChange={(e) => setStopLoss(parseFloat(e.target.value) || 0)}
                  min={0.1} max={50} step={0.5}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Take Profit %
                </label>
                <input type="number" value={takeProfit}
                  onChange={(e) => setTakeProfit(parseFloat(e.target.value) || 0)}
                  min={0.1} max={100} step={0.5}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={trailingStopEnabled}
                  onChange={(e) => setTrailingStopEnabled(e.target.checked)}
                  className="rounded border-border/50" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Trailing Stop %
                </span>
              </label>
              {trailingStopEnabled && (
                <input type="number" value={trailingStop}
                  onChange={(e) => setTrailingStop(parseFloat(e.target.value) || 0)}
                  min={0.1} max={50} step={0.5}
                  className="h-9 w-32 rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              )}
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={exitAfterBarsEnabled}
                  onChange={(e) => setExitAfterBarsEnabled(e.target.checked)}
                  className="rounded border-border/50" />
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Exit After N Bars
                </span>
              </label>
              {exitAfterBarsEnabled && (
                <input type="number" value={exitAfterBars}
                  onChange={(e) => setExitAfterBars(parseInt(e.target.value) || 1)}
                  min={1} max={500} step={1}
                  className="h-9 w-32 rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              )}
            </div>
          </AccordionSection>

          {/* Symbol Universe */}
          <AccordionSection
            title="Symbol Universe"
            badge={symbols.length > 0 ? symbols[0] : undefined}
          >
            <div className="flex flex-wrap gap-1.5 mb-2">
              {symbols.map((s) => (
                <span key={s}
                  className="inline-flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded bg-muted border border-border/50">
                  {s}
                  <button type="button" onClick={() => setSymbols((prev) => prev.filter((x) => x !== s))}
                    className="text-muted-foreground hover:text-red-400 transition-colors ml-0.5">×</button>
                </span>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value.toUpperCase())}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === ",") {
                    e.preventDefault();
                    addSymbol(symbolInput);
                  }
                }}
                placeholder="Add symbol (Enter)"
                className="h-9 flex-1 rounded-md border border-border/50 bg-background px-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
              <button type="button" onClick={() => addSymbol(symbolInput)}
                className="h-9 px-3 rounded-md border border-border/50 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors">
                Add
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              First symbol is used as default for backtesting.
            </p>
          </AccordionSection>

          {/* Execution Settings */}
          <AccordionSection title="Execution Settings">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Commission %
                </label>
                <input type="number" value={commissionPct}
                  onChange={(e) => setCommissionPct(parseFloat(e.target.value) || 0)}
                  min={0} max={5} step={0.01}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Slippage %
                </label>
                <input type="number" value={slippagePct}
                  onChange={(e) => setSlippagePct(parseFloat(e.target.value) || 0)}
                  min={0} max={5} step={0.01}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
            </div>
          </AccordionSection>

          {/* Risk Controls */}
          <AccordionSection title="Risk Controls">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Cooldown (bars)
                </label>
                <input type="number" value={cooldownBars}
                  onChange={(e) => setCooldownBars(parseInt(e.target.value) || 0)}
                  min={0} max={500}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
                <p className="text-[10px] text-muted-foreground mt-0.5">0 = no cooldown</p>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Max Trades/Day
                </label>
                <input type="number" value={maxTradesPerDay}
                  onChange={(e) => setMaxTradesPerDay(parseInt(e.target.value) || 0)}
                  min={0} max={100}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
                <p className="text-[10px] text-muted-foreground mt-0.5">0 = unlimited</p>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Max Exposure %
                </label>
                <input type="number" value={maxExposurePct}
                  onChange={(e) => setMaxExposurePct(parseFloat(e.target.value) || 100)}
                  min={1} max={100}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Daily Loss Limit %
                </label>
                <input type="number" value={maxLossPct}
                  onChange={(e) => setMaxLossPct(parseFloat(e.target.value) || 0)}
                  min={0} max={100} step={0.5}
                  className="mt-1 h-9 w-full rounded-md border border-border/50 bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-ring/40" />
                <p className="text-[10px] text-muted-foreground mt-0.5">0 = no limit</p>
              </div>
            </div>
          </AccordionSection>
        </div>

        {/* Right: Diagnostics & Explainer */}
        <div className="space-y-4">
          <DiagnosticPanel report={diagnostics} loading={diagLoading} />
          <ExplainerPanel explanation={explanation} loading={explainLoading} />
        </div>
      </div>
    </div>
  );
}
