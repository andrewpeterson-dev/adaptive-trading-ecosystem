"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import { ArrowLeft, BrainCircuit, Plus, Play, Save, RotateCcw, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ConditionGroup as ConditionGroupComponent } from "./ConditionGroup";
import { AccordionSection } from "./AccordionSection";
import { DiagnosticPanel } from "./DiagnosticPanel";
import { ExplainerPanel } from "./ExplainerPanel";
import { AIStrategyGeneratorDialog } from "./AIStrategyGeneratorDialog";
import { IndicatorChart } from "@/components/charts/IndicatorChart";
import { PageHeader } from "@/components/layout/PageHeader";
import type {
  ConditionGroup,
  StrategyCondition,
  Strategy,
  StrategyAiContext,
  StrategyRecord,
  DiagnosticReport,
  StrategyExplanation,
  Action,
  LogicalJoiner,
  StrategyType,
} from "@/types/strategy";
import { useStrategyBuilderStore } from "@/stores/strategy-builder-store";
import type { GeneratedStrategyResponse } from "@/lib/cerberus-api";

// ── Helpers ────────────────────────────────────────────────────────────────

type ExitLogic = "stop_target" | "indicator_reversal" | "time_stop" | "hybrid";
type OrderType = "market" | "limit" | "stop";
type BacktestPeriod = "3M" | "6M" | "1Y" | "2Y";

function genId(): string {
  return `id_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function emptyCondition(): StrategyCondition {
  return {
    id: genId(),
    indicator: "",
    operator: "<",
    value: 30,
    params: {},
    joiner: "AND",
    action: "BUY",
  };
}

function emptyGroup(index = 0): ConditionGroup {
  return {
    id: genId(),
    label: `Group ${String.fromCharCode(65 + index)}`,
    joiner: "OR",
    conditions: [emptyCondition()],
  };
}

function describeCondition(condition: StrategyCondition): string {
  if (!condition.indicator) return "Incomplete condition";
  const indicator = condition.indicator.toUpperCase().replace(/_/g, " ");
  const params = Object.values(condition.params);
  const paramLabel = params.length > 0 ? `(${params.join(", ")})` : "";
  const target = condition.compare_to
    ? condition.compare_to.replace(/_/g, " ").toUpperCase()
    : String(condition.value);
  return `${indicator}${paramLabel} ${condition.operator} ${target}`;
}

function buildLogicString(groups: ConditionGroup[], action: Action): string {
  const groupParts = groups
    .map((g) => {
      const activeConditions = g.conditions.filter((c) => c.indicator);
      const condParts = activeConditions.map((c) => {
          const paramStr = Object.values(c.params).join(",");
          const ind = c.indicator.toUpperCase().replace(/_/g, " ");
          const fieldSuffix = c.field ? `.${String(c.field).toUpperCase()}` : "";
          const indFmt = paramStr ? `${ind}(${paramStr})${fieldSuffix}` : `${ind}${fieldSuffix}`;
          const target = c.compare_to ? String(c.compare_to).replace(/_/g, " ") : c.value;
          return `${indFmt} ${c.operator} ${target}`;
        });
      if (condParts.length === 0) return null;
      return {
        joiner: (g.joiner ?? "OR") as LogicalJoiner,
        logic:
          condParts.length === 1
            ? condParts[0]
            : `(${condParts
                .map((part, index) =>
                  index === 0
                    ? part
                    : `${activeConditions[index].joiner ?? "AND"} ${part}`
                )
                .join(" ")})`,
      };
    })
    .filter((group): group is { joiner: LogicalJoiner; logic: string } => Boolean(group));
  if (groupParts.length === 0) return "";
  const [firstGroup, ...remainingGroups] = groupParts;
  return `IF ${[
    firstGroup.logic,
    ...remainingGroups.map((group) => `${group.joiner} ${group.logic}`),
  ].join(" ")} THEN ${action}`;
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
  const [strategyType, setStrategyType] = useState<StrategyType>("manual");
  const [sourcePrompt, setSourcePrompt] = useState("");
  const [aiContext, setAiContext] = useState<StrategyAiContext>({});
  const [isAIGeneratorOpen, setIsAIGeneratorOpen] = useState(false);

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
  const [exitLogic, setExitLogic] = useState<ExitLogic>("stop_target");

  // Universe
  const [symbols, setSymbols] = useState<string[]>(["SPY"]);
  const [symbolInput, setSymbolInput] = useState("");

  // Execution
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [backtestPeriod, setBacktestPeriod] = useState<BacktestPeriod>("1Y");
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
  const aiBaselineRef = useRef<string | null>(null);

  // ── Draft persistence (create mode only) ────────────────────────────────
  const DRAFT_KEY = "strategy_builder_draft";
  const buildFingerprint = useCallback((draft?: {
    name: string;
    description: string;
    action: Action;
    timeframe: string;
    conditionGroups: ConditionGroup[];
    stopLoss: number;
    takeProfit: number;
    positionSize: number;
    symbols: string[];
    orderType: OrderType;
    backtestPeriod: BacktestPeriod;
    exitLogic: ExitLogic;
    commissionPct: number;
    slippagePct: number;
    trailingStopEnabled: boolean;
    trailingStop: number;
    exitAfterBarsEnabled: boolean;
    exitAfterBars: number;
    cooldownBars: number;
    maxTradesPerDay: number;
    maxExposurePct: number;
    maxLossPct: number;
  }) => JSON.stringify(
    draft ?? {
      name,
      description,
      action,
      timeframe,
      conditionGroups,
      stopLoss,
      takeProfit,
      positionSize,
      symbols,
      orderType,
      backtestPeriod,
      exitLogic,
      commissionPct,
      slippagePct,
      trailingStopEnabled,
      trailingStop,
      exitAfterBarsEnabled,
      exitAfterBars,
      cooldownBars,
      maxTradesPerDay,
      maxExposurePct,
      maxLossPct,
    }
  ), [
    action,
    backtestPeriod,
    commissionPct,
    conditionGroups,
    cooldownBars,
    description,
    exitLogic,
    exitAfterBars,
    exitAfterBarsEnabled,
    maxExposurePct,
    maxLossPct,
    maxTradesPerDay,
    name,
    orderType,
    positionSize,
    slippagePct,
    stopLoss,
    symbols,
    takeProfit,
    timeframe,
    trailingStop,
    trailingStopEnabled,
  ]);
  const featureSignals = aiContext.feature_signals ?? [];
  const learningMethods = aiContext.learning_plan?.methods ?? [];

  useEffect(() => {
    if (mode !== "create") return;
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return;
      const d = JSON.parse(raw);
      if (d.name) setName(d.name);
      if (d.description) setDescription(d.description);
      if (d.action) setAction(d.action);
      if (d.timeframe) setTimeframe(d.timeframe);
      if (d.strategyType) setStrategyType(d.strategyType);
      if (d.sourcePrompt) setSourcePrompt(d.sourcePrompt);
      if (d.aiContext) setAiContext(d.aiContext);
      if (d.conditionGroups?.length) setConditionGroups(d.conditionGroups);
      if (d.stopLoss != null) setStopLoss(d.stopLoss);
      if (d.takeProfit != null) setTakeProfit(d.takeProfit);
      if (d.positionSize != null) setPositionSize(d.positionSize);
      if (d.trailingStopEnabled != null) setTrailingStopEnabled(d.trailingStopEnabled);
      if (d.trailingStop != null) setTrailingStop(d.trailingStop);
      if (d.exitAfterBarsEnabled != null) setExitAfterBarsEnabled(d.exitAfterBarsEnabled);
      if (d.exitAfterBars != null) setExitAfterBars(d.exitAfterBars);
      if (d.exitLogic) setExitLogic(d.exitLogic);
      if (d.symbols?.length) setSymbols(d.symbols);
      if (d.orderType) setOrderType(d.orderType);
      if (d.backtestPeriod) setBacktestPeriod(d.backtestPeriod);
      if (d.commissionPct != null) setCommissionPct(d.commissionPct);
      if (d.slippagePct != null) setSlippagePct(d.slippagePct);
      if (d.cooldownBars != null) setCooldownBars(d.cooldownBars);
      if (d.maxTradesPerDay != null) setMaxTradesPerDay(d.maxTradesPerDay);
      if (d.maxExposurePct != null) setMaxExposurePct(d.maxExposurePct);
      if (d.maxLossPct != null) setMaxLossPct(d.maxLossPct);
    } catch { /* ignore corrupt draft */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (mode !== "create") return;
    try {
      localStorage.setItem(DRAFT_KEY, JSON.stringify({
        name, description, action, timeframe, conditionGroups,
        stopLoss, takeProfit, positionSize,
        trailingStopEnabled, trailingStop,
        exitAfterBarsEnabled, exitAfterBars,
        exitLogic, orderType, backtestPeriod,
        symbols, commissionPct, slippagePct,
        cooldownBars, maxTradesPerDay, maxExposurePct, maxLossPct,
        strategyType, sourcePrompt, aiContext,
      }));
    } catch { /* ignore */ }
  }, [
    mode, name, description, action, timeframe, conditionGroups,
    stopLoss, takeProfit, positionSize,
    trailingStopEnabled, trailingStop,
    exitAfterBarsEnabled, exitAfterBars,
    exitLogic, orderType, backtestPeriod,
    symbols, commissionPct, slippagePct,
    cooldownBars, maxTradesPerDay, maxExposurePct, maxLossPct,
    strategyType, sourcePrompt, aiContext,
  ]);

  // ── Consume pending spec from Cerberus chat ────────────────────────────

  useEffect(() => {
    if (mode !== "create") return;
    const spec = useStrategyBuilderStore.getState().consumePendingSpec();
    if (!spec) return;
    const builderPreferences = spec.aiContext?.builder_preferences;
    setName(spec.name);
    setDescription(spec.description);
    setAction(spec.action);
    setStopLoss(spec.stopLoss);
    setTakeProfit(spec.takeProfit);
    setPositionSize(spec.positionSize);
    setTimeframe(spec.timeframe);
    setStrategyType(spec.strategyType ?? "ai_generated");
    setSourcePrompt(spec.sourcePrompt ?? "");
    setAiContext(spec.aiContext ?? {});
    setOrderType((builderPreferences?.order_type as OrderType | undefined) ?? "market");
    setBacktestPeriod(
      (builderPreferences?.backtest_period as BacktestPeriod | undefined) ?? "1Y"
    );
    setExitLogic(
      (builderPreferences?.exit_logic as ExitLogic | undefined) ?? "stop_target"
    );
    if (spec.symbols?.length) {
      setSymbols(spec.symbols);
    }
    if (spec.conditionGroups?.length) {
      setConditionGroups(spec.conditionGroups);
    } else if (spec.conditions.length > 0) {
      setConditionGroups([{
        id: genId(),
        label: "Group A",
        conditions: spec.conditions,
      }]);
    }
    aiBaselineRef.current = buildFingerprint({
      name: spec.name,
      description: spec.description,
      action: spec.action,
      timeframe: spec.timeframe,
      conditionGroups: spec.conditionGroups?.length
        ? spec.conditionGroups
        : [{
            id: genId(),
            label: "Group A",
            conditions: spec.conditions,
          }],
      stopLoss: spec.stopLoss,
      takeProfit: spec.takeProfit,
      positionSize: spec.positionSize,
      symbols: spec.symbols?.length ? spec.symbols : ["SPY"],
      orderType: (builderPreferences?.order_type as OrderType | undefined) ?? "market",
      backtestPeriod:
        (builderPreferences?.backtest_period as BacktestPeriod | undefined) ?? "1Y",
      exitLogic:
        (builderPreferences?.exit_logic as ExitLogic | undefined) ?? "stop_target",
      commissionPct,
      slippagePct,
      trailingStopEnabled: false,
      trailingStop,
      exitAfterBarsEnabled: false,
      exitAfterBars,
      cooldownBars,
      maxTradesPerDay,
      maxExposurePct,
      maxLossPct,
    });
    localStorage.removeItem(DRAFT_KEY);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Populate from initialStrategy (edit mode) ──────────────────────────

  useEffect(() => {
    if (!initialStrategy) return;
    const builderPreferences = initialStrategy.ai_context?.builder_preferences;
    setName(initialStrategy.name);
    setDescription(initialStrategy.description || "");
    setAction(initialStrategy.action as Action);
    setStrategyType(initialStrategy.strategy_type ?? "manual");
    setSourcePrompt(initialStrategy.source_prompt ?? "");
    setAiContext(initialStrategy.ai_context ?? {});
    setStopLoss((initialStrategy.stop_loss_pct || 0.02) * 100);
    setTakeProfit((initialStrategy.take_profit_pct || 0.05) * 100);
    setPositionSize((initialStrategy.position_size_pct || 0.1) * 100);
    setTimeframe(initialStrategy.timeframe || "1D");
    setSymbols(initialStrategy.symbols?.length ? initialStrategy.symbols : ["SPY"]);
    setOrderType((builderPreferences?.order_type as OrderType | undefined) ?? "market");
    setBacktestPeriod(
      (builderPreferences?.backtest_period as BacktestPeriod | undefined) ?? "1Y"
    );
    setExitLogic(
      (builderPreferences?.exit_logic as ExitLogic | undefined) ?? "stop_target"
    );
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
          joiner: (g as ConditionGroup).joiner ?? "OR",
          conditions: g.conditions.map((c) => ({
            id: genId(),
            indicator: c.indicator,
            operator: c.operator as StrategyCondition["operator"],
            value: c.value,
            compare_to: c.compare_to,
            joiner: (c as StrategyCondition).joiner ?? "AND",
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
            joiner: (c as StrategyCondition).joiner ?? "AND",
            params: c.params || {},
            action: (c.action as Action) || (initialStrategy.action as Action),
          })),
        },
      ]);
    }
    if (initialStrategy.diagnostics) {
      setDiagnostics(initialStrategy.diagnostics as DiagnosticReport);
    }
    if ((initialStrategy.strategy_type ?? "manual") !== "manual") {
      aiBaselineRef.current = buildFingerprint({
        name: initialStrategy.name,
        description: initialStrategy.description || "",
        action: initialStrategy.action as Action,
        timeframe: initialStrategy.timeframe || "1D",
        conditionGroups: initialStrategy.condition_groups?.length
          ? initialStrategy.condition_groups.map((g, gi) => ({
              id: g.id ?? `initial_${gi}`,
              label: g.label ?? `Group ${String.fromCharCode(65 + gi)}`,
              joiner: (g as ConditionGroup).joiner ?? "OR",
              conditions: g.conditions.map((c, ci) => ({
                id: `${g.id ?? gi}_${ci}`,
                indicator: c.indicator,
                operator: c.operator as StrategyCondition["operator"],
                value: c.value,
                compare_to: c.compare_to,
                field: c.field,
                joiner: (c as StrategyCondition).joiner ?? "AND",
                params: c.params || {},
                action: (c.action as Action) || (initialStrategy.action as Action),
              })),
            }))
          : [{
              id: "initial_group",
              label: "Group A",
              conditions: (initialStrategy.conditions || []).map((c, ci) => ({
                id: `initial_${ci}`,
                indicator: c.indicator,
                operator: c.operator as StrategyCondition["operator"],
                value: c.value,
                compare_to: c.compare_to,
                field: c.field,
                joiner: (c as StrategyCondition).joiner ?? "AND",
                params: c.params || {},
                action: (c.action as Action) || (initialStrategy.action as Action),
              })),
            }],
        stopLoss: (initialStrategy.stop_loss_pct || 0.02) * 100,
        takeProfit: (initialStrategy.take_profit_pct || 0.05) * 100,
        positionSize: (initialStrategy.position_size_pct || 0.1) * 100,
        symbols: initialStrategy.symbols?.length ? initialStrategy.symbols : ["SPY"],
        orderType: (builderPreferences?.order_type as OrderType | undefined) ?? "market",
        backtestPeriod:
          (builderPreferences?.backtest_period as BacktestPeriod | undefined) ?? "1Y",
        exitLogic:
          (builderPreferences?.exit_logic as ExitLogic | undefined) ?? "stop_target",
        commissionPct: (initialStrategy.commission_pct ?? 0.001) * 100,
        slippagePct: (initialStrategy.slippage_pct ?? 0.0005) * 100,
        trailingStopEnabled: initialStrategy.trailing_stop_pct != null,
        trailingStop: (initialStrategy.trailing_stop_pct ?? 0) * 100,
        exitAfterBarsEnabled: initialStrategy.exit_after_bars != null,
        exitAfterBars: initialStrategy.exit_after_bars ?? 10,
        cooldownBars: initialStrategy.cooldown_bars ?? 0,
        maxTradesPerDay: initialStrategy.max_trades_per_day ?? 0,
        maxExposurePct: (initialStrategy.max_exposure_pct ?? 1.0) * 100,
        maxLossPct: (initialStrategy.max_loss_pct ?? 0) * 100,
      });
    } else {
      aiBaselineRef.current = null;
    }
  }, [initialStrategy]);

  useEffect(() => {
    if (strategyType !== "ai_generated" || !aiBaselineRef.current) return;
    if (buildFingerprint() !== aiBaselineRef.current) {
      setStrategyType("custom");
    }
  }, [buildFingerprint, strategyType]);

  // ── Group / condition handlers ─────────────────────────────────────────

  const addGroup = useCallback(() => {
    setConditionGroups((prev) => [...prev, emptyGroup(prev.length)]);
  }, []);

  const updateGroupJoiner = useCallback((groupIndex: number, joiner: LogicalJoiner) => {
    setConditionGroups((prev) =>
      prev.map((group, index) =>
        index === groupIndex ? { ...group, joiner } : group
      )
    );
  }, []);

  const removeGroup = useCallback((groupIndex: number) => {
    setConditionGroups((prev) =>
      prev
        .filter((_, i) => i !== groupIndex)
        .map((group, index) =>
          index === 0 ? { ...group, joiner: "OR" } : group
        )
    );
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
    try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
    setConditionGroups([emptyGroup(0)]);
    setDiagnostics(null);
    setExplanation(null);
    setName("My Strategy");
    setDescription("");
    setStrategyType("manual");
    setSourcePrompt("");
    setAiContext({});
    setSaveStatus("idle");
    setIndicatorPreviews({});
    setSymbols(["SPY"]);
    setStopLoss(2);
    setTakeProfit(5);
    setPositionSize(10);
    setOrderType("market");
    setBacktestPeriod("1Y");
    setExitLogic("stop_target");
    setTrailingStopEnabled(false);
    setExitAfterBarsEnabled(false);
    aiBaselineRef.current = null;
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
  const allConditionGroupsWithRules = conditionGroups.filter((group) =>
    group.conditions.some((condition) => condition.indicator)
  );

  // ── Auto-diagnostics (debounced, uses apiFetch for auth) ───────────────

  const conditionKey = conditionGroups
    .flatMap((g) => g.conditions)
    .map((c) =>
      `${c.indicator}:${c.operator}:${c.value}:${c.compare_to ?? ""}:${c.joiner ?? "AND"}:${JSON.stringify(c.params)}`
    )
    .join("|");
  const previewKey = `${conditionKey}:${symbols.join(",")}:${timeframe}`;

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
              body: JSON.stringify({
                indicator: c.indicator,
                params: c.params,
                symbol: symbols[0] ?? "SPY",
                timeframe,
              }),
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
  }, [previewKey]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const applyGeneratedStrategy = useCallback((result: GeneratedStrategyResponse) => {
    const draft = result.builder_draft;
    const builderPreferences = draft.aiContext?.builder_preferences;
    const groups = (draft.conditionGroups as unknown as ConditionGroup[] | undefined)
      ?? [{
        id: genId(),
        label: "Group A",
        conditions: (draft.conditions as unknown as StrategyCondition[] | undefined) ?? [],
      }];

    setName(draft.name);
    setDescription(draft.description);
    setAction(draft.action);
    setStopLoss(draft.stopLoss);
    setTakeProfit(draft.takeProfit);
    setPositionSize(draft.positionSize);
    setTimeframe(draft.timeframe);
    setConditionGroups(groups);
    setSymbols(draft.symbols?.length ? draft.symbols : ["SPY"]);
    setOrderType((builderPreferences?.order_type as OrderType | undefined) ?? "market");
    setBacktestPeriod(
      (builderPreferences?.backtest_period as BacktestPeriod | undefined) ?? "1Y"
    );
    setExitLogic(
      (builderPreferences?.exit_logic as ExitLogic | undefined) ?? "stop_target"
    );
    setStrategyType(draft.strategyType ?? "ai_generated");
    setSourcePrompt(draft.sourcePrompt ?? result.prompt);
    setAiContext(draft.aiContext ?? {});
    setSaveStatus("idle");
    setExplanation(null);
    setDiagnostics(null);
    aiBaselineRef.current = buildFingerprint({
      name: draft.name,
      description: draft.description,
      action: draft.action,
      timeframe: draft.timeframe,
      conditionGroups: groups,
      stopLoss: draft.stopLoss,
      takeProfit: draft.takeProfit,
      positionSize: draft.positionSize,
      symbols: draft.symbols?.length ? draft.symbols : ["SPY"],
      orderType: (builderPreferences?.order_type as OrderType | undefined) ?? "market",
      backtestPeriod:
        (builderPreferences?.backtest_period as BacktestPeriod | undefined) ?? "1Y",
      exitLogic:
        (builderPreferences?.exit_logic as ExitLogic | undefined) ?? "stop_target",
      commissionPct,
      slippagePct,
      trailingStopEnabled,
      trailingStop,
      exitAfterBarsEnabled,
      exitAfterBars,
      cooldownBars,
      maxTradesPerDay,
      maxExposurePct,
      maxLossPct,
    });
    try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
  }, [
    buildFingerprint,
    commissionPct,
    cooldownBars,
    exitAfterBars,
    exitAfterBarsEnabled,
    maxExposurePct,
    maxLossPct,
    maxTradesPerDay,
    slippagePct,
    trailingStop,
    trailingStopEnabled,
  ]);

  // ── Save / Update ────────────────────────────────────────────────────────

  const saveStrategy = async () => {
    if (!canSave) {
      setSaveStatus("error");
      return;
    }
    const nextAiContext: StrategyAiContext = {
      ...aiContext,
      builder_preferences: {
        order_type: orderType,
        backtest_period: backtestPeriod,
        exit_logic: exitLogic,
      },
    };

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
      strategy_type: strategyType,
      source_prompt: sourcePrompt || null,
      ai_context: nextAiContext,
    };

    try {
      if (mode === "edit" && initialStrategy) {
        await apiFetch(`/api/strategies/${initialStrategy.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
      } else {
        const created = await apiFetch<{ id: number }>("/api/strategies/create", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        // Clear draft after successful save
        try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
        setSaveStatus("saved");
        setTimeout(() => router.push(`/edit/${created.id}`), 1200);
        return;
      }
      setAiContext(nextAiContext);
      setSaveStatus("saved");
      setTimeout(() => setSaveStatus("idle"), 3000);
    } catch {
      setSaveStatus("error");
    }
  };

  // ── Derived state ────────────────────────────────────────────────────────

  const logicString = buildLogicString(conditionGroups, action);
  const validationIssues = [
    !name.trim() ? "Name is required." : null,
    symbols.length === 0 ? "Add at least one symbol or universe member." : null,
    stopLoss <= 0 ? "Stop loss must be greater than 0%." : null,
    takeProfit <= 0 ? "Take profit must be greater than 0%." : null,
    positionSize < 0 || positionSize > 100
      ? "Position size must stay between 0% and 100%."
      : null,
    !orderType ? "Choose an order type." : null,
    !backtestPeriod ? "Choose a backtest period." : null,
    !exitLogic ? "Choose an exit logic profile." : null,
    allValidConditions.length === 0
      ? "Add at least one complete entry condition."
      : null,
  ].filter(Boolean) as string[];
  const canSave = validationIssues.length === 0 && saveStatus !== "saving";
  const builderHint =
    validationIssues.length > 0
      ? `Finish the required builder inputs before saving: ${validationIssues.join(" ")}`
      : "Builder state is complete. Review the logic tree, run diagnostics, then save or backtest.";
  const exitLogicLabel = {
    stop_target: "Stops + targets",
    indicator_reversal: "Indicator reversal",
    time_stop: "Time stop",
    hybrid: "Hybrid exit",
  }[exitLogic];
  const orderTypeLabel = orderType.toUpperCase();

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
    <div className="app-page">
      <AIStrategyGeneratorDialog
        open={isAIGeneratorOpen}
        onOpenChange={setIsAIGeneratorOpen}
        onApplyDraft={applyGeneratedStrategy}
      />
      <PageHeader
        eyebrow="Builder"
        title={mode === "edit" ? "Edit Strategy" : "Strategy Builder"}
        description={
          mode === "edit"
            ? `Refine strategy #${initialStrategy?.id}, inspect its AI metadata, and keep the underlying builder in control of execution.`
            : "Use Cerberus to interview the strategy idea, translate it into executable logic, and hand you a builder-ready draft before anything is saved or deployed."
        }
        meta={
          <>
            {allValidConditions.length > 0 && (
              <span className="app-pill font-mono tracking-normal">
                {allValidConditions.length} active condition
                {allValidConditions.length !== 1 ? "s" : ""}
              </span>
            )}
            <span className="app-pill font-mono tracking-normal">
              {strategyType === "ai_generated"
                ? "Cerberus Generated"
                : strategyType === "custom"
                  ? "Custom"
                  : "Manual"}
            </span>
          </>
        }
        actions={
          <div className="flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => setIsAIGeneratorOpen(true)}
              className="app-button-primary"
            >
              <BrainCircuit className="h-3.5 w-3.5" />
              Build with Cerberus
            </button>
            <button
              type="button"
              onClick={resetBuilder}
              className="app-button-ghost"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset
            </button>
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex">
                    <button
                      type="button"
                      onClick={runExplainer}
                      disabled={allValidConditions.length === 0 || explainLoading}
                      className="app-button-ghost disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      <Zap className="h-3.5 w-3.5" />
                      {explainLoading ? "Analyzing…" : "Analyze"}
                    </button>
                  </span>
                </TooltipTrigger>
                {allValidConditions.length === 0 && (
                  <TooltipContent>Add at least one entry condition to analyze</TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
            {mode === "edit" && initialStrategy && (
              <button
                onClick={() => router.push(`/backtest/${initialStrategy.id}`)}
                className="app-button-ghost text-amber-500"
              >
                <Play className="h-3.5 w-3.5" />
                Backtest
              </button>
            )}
            <TooltipProvider delayDuration={200}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex">
                    <button
                      type="button"
                      onClick={saveStrategy}
                      disabled={!canSave}
                      className="app-button-secondary disabled:cursor-not-allowed disabled:translate-y-0 disabled:opacity-40"
                    >
                      <Save className="h-3.5 w-3.5" />
                      {saveStatus === "saving"
                        ? "Saving..."
                        : saveStatus === "saved"
                          ? "Saved ✓"
                          : saveStatus === "error"
                            ? "Failed — Retry"
                            : mode === "edit"
                              ? "Update Strategy"
                              : "Save"}
                    </button>
                  </span>
                </TooltipTrigger>
                {!canSave && validationIssues.length > 0 && (
                  <TooltipContent>{validationIssues[0]}</TooltipContent>
                )}
              </Tooltip>
            </TooltipProvider>
          </div>
        }
      />

      <div className="app-segmented">
        <button
          onClick={() => { setStrategyType("manual"); setSourcePrompt(""); setAiContext({}); aiBaselineRef.current = null; }}
          className={cn("app-segment", strategyType === "manual" && "app-toggle-active")}
        >
          Manual
        </button>
        <button
          onClick={() => setIsAIGeneratorOpen(true)}
          className={cn("app-segment", strategyType === "ai_generated" && "app-toggle-active")}
        >
          AI-Assisted
        </button>
        <button
          onClick={() => setStrategyType("custom")}
          className={cn("app-segment", (strategyType === "custom") && "app-toggle-active")}
        >
          From Template
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-4">
          <div className="app-panel p-5 sm:p-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="app-label">
                  Strategy Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="app-input mt-2"
                />
              </div>
              <div className="md:col-span-1">
                <label className="app-label">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe the strategy, setup quality, and why the edge should persist."
                  rows={4}
                  className="app-input mt-2 min-h-[112px] resize-y py-3"
                />
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
              <div>
                <label className="app-label">
                  Action
                </label>
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value as Action)}
                  className="app-select mt-2 text-sm font-medium"
                >
                  <option value="BUY">BUY</option>
                  <option value="SELL">SELL</option>
                </select>
              </div>
              <div>
                <label className="app-label">
                  Timeframe
                </label>
                <select
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value)}
                  className="app-select mt-2 text-sm"
                >
                  {["1m", "5m", "15m", "1H", "4H", "1D", "1W"].map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="app-label">
                  Position %
                </label>
                <input
                  type="number"
                  value={positionSize}
                  onChange={(e) => setPositionSize(parseFloat(e.target.value) || 0)}
                  min={0} max={100} step={1}
                  className="app-input mt-2 font-mono text-right"
                />
              </div>
              <div>
                <label className="app-label">
                  Order Type
                </label>
                <select
                  value={orderType}
                  onChange={(e) => setOrderType(e.target.value as OrderType)}
                  className="app-select mt-2 text-sm"
                >
                  <option value="market">Market</option>
                  <option value="limit">Limit</option>
                  <option value="stop">Stop</option>
                </select>
              </div>
              <div>
                <label className="app-label">
                  Backtest Period
                </label>
                <select
                  value={backtestPeriod}
                  onChange={(e) => setBacktestPeriod(e.target.value as BacktestPeriod)}
                  className="app-select mt-2 text-sm"
                >
                  <option value="3M">3M</option>
                  <option value="6M">6M</option>
                  <option value="1Y">1Y</option>
                  <option value="2Y">2Y</option>
                </select>
              </div>
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-[1.3fr_1fr]">
              <div className="rounded-[24px] border border-border/60 bg-muted/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="app-label">Symbol / Universe</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Required. The first symbol anchors diagnostics and backtests.
                    </p>
                  </div>
                  <span className="app-pill font-mono tracking-normal">
                    {symbols.length} symbol{symbols.length === 1 ? "" : "s"}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {symbols.map((symbol) => (
                    <span
                      key={symbol}
                      className="app-pill items-center gap-1 px-2.5 py-1 text-xs font-mono tracking-normal"
                    >
                      {symbol}
                      <button
                        type="button"
                        onClick={() =>
                          setSymbols((prev) => prev.filter((value) => value !== symbol))
                        }
                        className="ml-0.5 text-muted-foreground transition-colors hover:text-red-400"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
                <div className="mt-3 flex flex-col gap-2 sm:flex-row">
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
                    className="app-input flex-1 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => addSymbol(symbolInput)}
                    className="app-button-secondary h-11 px-5"
                  >
                    Add
                  </button>
                </div>
              </div>

              <div className="rounded-[24px] border border-border/60 bg-muted/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="app-label">Exit Profile</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Required. Define how the strategy gets out, not just how it gets in.
                    </p>
                  </div>
                  <span className="app-pill font-mono tracking-normal">
                    {exitLogicLabel}
                  </span>
                </div>
                <select
                  value={exitLogic}
                  onChange={(e) => setExitLogic(e.target.value as ExitLogic)}
                  className="app-select mt-3 text-sm"
                >
                  <option value="stop_target">Stops + targets</option>
                  <option value="indicator_reversal">Indicator reversal</option>
                  <option value="time_stop">Time stop</option>
                  <option value="hybrid">Hybrid exit</option>
                </select>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                  <div className="rounded-2xl border border-border/60 bg-background/60 px-3 py-2">
                    Stop Loss: <span className="font-mono text-foreground">{stopLoss}%</span>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/60 px-3 py-2">
                    Take Profit: <span className="font-mono text-foreground">{takeProfit}%</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-5 rounded-[24px] border border-border/60 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
              {builderHint}
            </div>

            {(strategyType !== "manual" || sourcePrompt || aiContext.overview) && (
              <div className="mt-5 rounded-3xl border border-sky-400/20 bg-sky-400/5 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-sky-400/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-sky-400">
                    Strategy Overview
                  </span>
                  {featureSignals.map((signal) => (
                    <span key={signal} className="rounded-full border border-border/60 px-2.5 py-1 text-[10px] font-mono text-muted-foreground">
                      {signal}
                    </span>
                  ))}
                  <span className="rounded-full border border-border/60 px-2.5 py-1 text-[10px] font-mono text-muted-foreground">
                    {orderTypeLabel}
                  </span>
                  <span className="rounded-full border border-border/60 px-2.5 py-1 text-[10px] font-mono text-muted-foreground">
                    {backtestPeriod}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-foreground">
                  {aiContext.overview || description || "Cerberus-generated strategy ready for inspection."}
                </p>
                {sourcePrompt && (
                  <div className="mt-3 rounded-2xl bg-background/60 px-3 py-2 text-xs text-muted-foreground">
                    <span className="font-semibold text-foreground">Prompt:</span> {sourcePrompt}
                  </div>
                )}
                {learningMethods.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {learningMethods.map((method) => (
                      <span key={method} className="rounded-full border border-emerald-400/20 bg-emerald-400/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-400">
                        {method.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="app-panel p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="app-label">
                Entry Conditions
              </h3>
              <span className="app-pill font-mono tracking-normal">
                {allValidConditions.length} active
              </span>
            </div>

            <div className="rounded-[22px] border border-border/60 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
              Define the entry tree one branch at a time: each branch can mix AND/OR rules internally, then you can join branches with their own AND/OR operator.
            </div>

            {conditionGroups.map((group, gi) => (
              <React.Fragment key={group.id}>
                {gi > 0 && (
                  <div className="flex items-center justify-center">
                    <select
                      value={group.joiner ?? "OR"}
                      onChange={(event) =>
                        updateGroupJoiner(gi, event.target.value as LogicalJoiner)
                      }
                      className="app-select h-10 rounded-full px-4 py-0 text-[11px] font-semibold uppercase tracking-[0.18em]"
                    >
                      <option value="AND">AND</option>
                      <option value="OR">OR</option>
                    </select>
                  </div>
                )}
                <ConditionGroupComponent
                  group={group}
                  groupIndex={gi}
                  totalGroups={conditionGroups.length}
                  onAddCondition={addCondition}
                  onRemoveCondition={removeCondition}
                  onUpdateCondition={updateCondition}
                  onRemoveGroup={removeGroup}
                />
              </React.Fragment>
            ))}

            <button
              onClick={addGroup}
              className="app-inset flex w-full items-center justify-center gap-1.5 py-4 text-sm text-muted-foreground hover:text-foreground"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Group
            </button>
          </div>

          <div className="app-panel space-y-4 p-5 sm:p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="app-label">Logic Preview</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Review the readable DSL and the branch tree before you save.
                </p>
              </div>
              <span className="app-pill font-mono tracking-normal">DSL</span>
            </div>

            <div className="dsl-code-block relative">
              <button
                onClick={() => { navigator.clipboard.writeText(logicString); }}
                className="absolute right-3 top-3 rounded-lg bg-slate-700/60 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-300 hover:bg-slate-600/80 transition-colors"
              >
                Copy DSL
              </button>
              <code className="break-all">
                {logicString
                  ? logicString.split(/\b/).map((token, i) => {
                      if (/^(IF|THEN|AND|OR)$/.test(token)) return <span key={i} className="token-keyword">{token}</span>;
                      if (/^(BUY|SELL)$/.test(token)) return <span key={i} className="token-keyword">{token}</span>;
                      if (/^[A-Z_]{2,}/.test(token)) return <span key={i} className="token-indicator">{token}</span>;
                      if (/^[<>=!]+$/.test(token)) return <span key={i} className="token-operator">{token}</span>;
                      if (/^\d/.test(token)) return <span key={i} className="token-value">{token}</span>;
                      return <span key={i}>{token}</span>;
                    })
                  : <span className="text-slate-500">IF [build at least one entry rule] THEN BUY</span>}
              </code>
            </div>

            {allConditionGroupsWithRules.length > 0 && (
              <div className="space-y-3">
                {allConditionGroupsWithRules.map((group, groupIndex) => (
                  <React.Fragment key={group.id}>
                    {groupIndex > 0 && (
                      <div className="flex items-center justify-center">
                        <span className="rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-400">
                          {group.joiner ?? "OR"}
                        </span>
                      </div>
                    )}
                    <div className="rounded-[22px] border border-border/60 bg-muted/20 p-4">
                      <p className="app-label">
                        {group.label ?? `Group ${String.fromCharCode(65 + groupIndex)}`}
                      </p>
                      <div className="mt-3 space-y-2">
                        {group.conditions
                          .filter((condition) => condition.indicator)
                          .map((condition, conditionIndex) => (
                            <div
                              key={condition.id}
                              className="rounded-2xl border border-border/60 bg-background/60 px-3 py-2 text-sm text-foreground"
                            >
                              {conditionIndex > 0 && (
                                <span className="mr-2 rounded-full border border-primary/20 bg-primary/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">
                                  {condition.joiner ?? "AND"}
                                </span>
                              )}
                              {describeCondition(condition)}
                            </div>
                          ))}
                      </div>
                    </div>
                  </React.Fragment>
                ))}
              </div>
            )}
          </div>

          {allValidConditions.length > 0 && Object.keys(indicatorPreviews).length > 0 && (
            <div className="app-panel space-y-3 p-5 sm:p-6">
              <div className="app-label">
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

          <AccordionSection title="Exit Conditions" defaultOpen badge={exitLogicLabel} borderColor="border-l-red-500">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="app-label">
                  Stop Loss %
                </label>
                <input type="number" value={stopLoss}
                  onChange={(e) => setStopLoss(parseFloat(e.target.value) || 0)}
                  min={0.1} max={50} step={0.5}
                  className="app-input mt-2 font-mono text-right" />
              </div>
              <div>
                <label className="app-label">
                  Take Profit %
                </label>
                <input type="number" value={takeProfit}
                  onChange={(e) => setTakeProfit(parseFloat(e.target.value) || 0)}
                  min={0.1} max={100} step={0.5}
                  className="app-input mt-2 font-mono text-right" />
              </div>
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={trailingStopEnabled}
                  onChange={(e) => setTrailingStopEnabled(e.target.checked)}
                  className="rounded border-border/50" />
                <span className="app-label">
                  Trailing Stop %
                </span>
              </label>
              {trailingStopEnabled && (
                <input type="number" value={trailingStop}
                  onChange={(e) => setTrailingStop(parseFloat(e.target.value) || 0)}
                  min={0.1} max={50} step={0.5}
                  className="app-input h-10 w-full max-w-[10rem] font-mono text-right" />
              )}
            </div>
            <div className="space-y-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={exitAfterBarsEnabled}
                  onChange={(e) => setExitAfterBarsEnabled(e.target.checked)}
                  className="rounded border-border/50" />
                <span className="app-label">
                  Exit After N Bars
                </span>
              </label>
              {exitAfterBarsEnabled && (
                <input type="number" value={exitAfterBars}
                  onChange={(e) => setExitAfterBars(parseInt(e.target.value) || 1)}
                  min={1} max={500} step={1}
                  className="app-input h-10 w-full max-w-[10rem] font-mono text-right" />
              )}
            </div>
          </AccordionSection>

          <AccordionSection title="Execution Settings" badge={orderTypeLabel} borderColor="border-l-slate-400">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="app-label">
                  Commission %
                </label>
                <input type="number" value={commissionPct}
                  onChange={(e) => setCommissionPct(parseFloat(e.target.value) || 0)}
                  min={0} max={5} step={0.01}
                  className="app-input mt-2 font-mono text-right" />
              </div>
              <div>
                <label className="app-label">
                  Slippage %
                </label>
                <input type="number" value={slippagePct}
                  onChange={(e) => setSlippagePct(parseFloat(e.target.value) || 0)}
                  min={0} max={5} step={0.01}
                  className="app-input mt-2 font-mono text-right" />
              </div>
              <div>
                <label className="app-label">
                  Order Type
                </label>
                <div className="mt-2 rounded-2xl border border-border/60 bg-background/60 px-3 py-3 text-sm text-foreground">
                  {orderTypeLabel}
                </div>
              </div>
              <div>
                <label className="app-label">
                  Backtest Period
                </label>
                <div className="mt-2 rounded-2xl border border-border/60 bg-background/60 px-3 py-3 text-sm text-foreground">
                  {backtestPeriod}
                </div>
              </div>
            </div>
          </AccordionSection>

          <AccordionSection title="Risk Controls" borderColor="border-l-amber-500">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="app-label">
                  Cooldown (bars)
                </label>
                <input type="number" value={cooldownBars}
                  onChange={(e) => setCooldownBars(parseInt(e.target.value) || 0)}
                  min={0} max={500}
                  className="app-input mt-2 font-mono text-right" />
                <p className="text-[10px] text-muted-foreground mt-0.5">0 = no cooldown</p>
              </div>
              <div>
                <label className="app-label">
                  Max Trades/Day
                </label>
                <input type="number" value={maxTradesPerDay}
                  onChange={(e) => setMaxTradesPerDay(parseInt(e.target.value) || 0)}
                  min={0} max={100}
                  className="app-input mt-2 font-mono text-right" />
                <p className="text-[10px] text-muted-foreground mt-0.5">0 = unlimited</p>
              </div>
              <div>
                <label className="app-label">
                  Max Exposure %
                </label>
                <input type="number" value={maxExposurePct}
                  onChange={(e) => setMaxExposurePct(parseFloat(e.target.value) || 100)}
                  min={1} max={100}
                  className="app-input mt-2 font-mono text-right" />
              </div>
              <div>
                <label className="app-label">
                  Daily Loss Limit %
                </label>
                <input type="number" value={maxLossPct}
                  onChange={(e) => setMaxLossPct(parseFloat(e.target.value) || 0)}
                  min={0} max={100} step={0.5}
                  className="app-input mt-2 font-mono text-right" />
                <p className="text-[10px] text-muted-foreground mt-0.5">0 = no limit</p>
              </div>
            </div>
          </AccordionSection>
        </div>

        <div className="space-y-4 lg:sticky lg:top-[calc(var(--status-bar-height)+1.75rem)] lg:self-start">
          {allValidConditions.length === 0 && !diagnostics && !explanation ? (
            <div className="app-panel p-5">
              <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full border border-border/60 bg-muted/40">
                  <Zap className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">Add your first entry condition</p>
                  <p className="mt-1 text-sm text-muted-foreground">Diagnostics will appear here as you build</p>
                </div>
                <div className="text-muted-foreground/40">
                  <ArrowLeft className="h-5 w-5" />
                </div>
              </div>
            </div>
          ) : (
            <>
              <DiagnosticPanel report={diagnostics} loading={diagLoading} />
              <ExplainerPanel explanation={explanation} loading={explainLoading} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
