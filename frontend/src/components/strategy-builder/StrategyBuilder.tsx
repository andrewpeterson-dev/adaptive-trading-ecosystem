"use client";

import React, { useState, useCallback, useEffect, useRef } from "react";
import { BrainCircuit, Plus, Play, Save, RotateCcw, Zap } from "lucide-react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api/client";
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
  StrategyType,
} from "@/types/strategy";
import { useStrategyBuilderStore } from "@/stores/strategy-builder-store";
import type { GeneratedStrategyResponse } from "@/lib/cerberus-api";

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
          const fieldSuffix = c.field ? `.${String(c.field).toUpperCase()}` : "";
          const indFmt = paramStr ? `${ind}(${paramStr})${fieldSuffix}` : `${ind}${fieldSuffix}`;
          const target = c.compare_to ? String(c.compare_to).replace(/_/g, " ") : c.value;
          return `${indFmt} ${c.operator} ${target}`;
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
    commissionPct,
    conditionGroups,
    cooldownBars,
    description,
    exitAfterBars,
    exitAfterBarsEnabled,
    maxExposurePct,
    maxLossPct,
    maxTradesPerDay,
    name,
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
      if (d.symbols?.length) setSymbols(d.symbols);
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
    symbols, commissionPct, slippagePct,
    cooldownBars, maxTradesPerDay, maxExposurePct, maxLossPct,
    strategyType, sourcePrompt, aiContext,
  ]);

  // ── Consume pending spec from Cerberus chat ────────────────────────────

  useEffect(() => {
    if (mode !== "create") return;
    const spec = useStrategyBuilderStore.getState().consumePendingSpec();
    if (!spec) return;
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
              conditions: g.conditions.map((c, ci) => ({
                id: `${g.id ?? gi}_${ci}`,
                indicator: c.indicator,
                operator: c.operator as StrategyCondition["operator"],
                value: c.value,
                compare_to: c.compare_to,
                field: c.field,
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
                params: c.params || {},
                action: (c.action as Action) || (initialStrategy.action as Action),
              })),
            }],
        stopLoss: (initialStrategy.stop_loss_pct || 0.02) * 100,
        takeProfit: (initialStrategy.take_profit_pct || 0.05) * 100,
        positionSize: (initialStrategy.position_size_pct || 0.1) * 100,
        symbols: initialStrategy.symbols?.length ? initialStrategy.symbols : ["SPY"],
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

  const applyGeneratedStrategy = useCallback((result: GeneratedStrategyResponse) => {
    const draft = result.builder_draft;
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
      ai_context: aiContext,
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
          <button
            type="button"
            onClick={runExplainer}
            disabled={allValidConditions.length === 0 || explainLoading}
            className="app-button-secondary disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Zap className="h-3.5 w-3.5" />
            {explainLoading ? "Analyzing…" : "Analyze"}
          </button>
          {mode === "edit" && initialStrategy && (
            <button
              onClick={() => router.push(`/backtest/${initialStrategy.id}`)}
              className="app-button-secondary text-amber-500"
            >
              <Play className="h-3.5 w-3.5" />
              Backtest
            </button>
          )}
          <button
            type="button"
            onClick={saveStrategy}
            disabled={allValidConditions.length === 0 || saveStatus === "saving"}
            className="app-button-primary disabled:cursor-not-allowed disabled:translate-y-0 disabled:opacity-40"
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
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
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
            <div>
                <label className="app-label">
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description..."
                  className="app-input mt-2"
              />
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-4">
            <div>
                <label className="app-label">
                Strategy Type
              </label>
              <select
                value={strategyType}
                onChange={(e) => {
                  const next = e.target.value as StrategyType;
                  setStrategyType(next);
                  if (next === "manual") {
                    setSourcePrompt("");
                    setAiContext({});
                    aiBaselineRef.current = null;
                  }
                }}
                  className="app-select mt-2 text-sm font-medium"
              >
                <option value="ai_generated">AI Generated</option>
                <option value="manual">Manual</option>
                <option value="custom">Custom</option>
              </select>
            </div>
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
                min={1} max={100} step={1}
                  className="app-input mt-2 font-mono text-right"
              />
            </div>
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
              className="app-inset flex w-full items-center justify-center gap-1.5 py-4 text-sm text-muted-foreground hover:text-foreground"
            >
              <Plus className="h-3.5 w-3.5" />
              Add OR Group
            </button>
          </div>

          {logicString && (
            <div className="app-inset p-4">
              <div className="app-label mb-2">
                Strategy Logic
              </div>
              <code className="text-sm font-mono text-primary break-all">{logicString}</code>
            </div>
          )}

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

          <AccordionSection title="Exit Conditions" defaultOpen>
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

          <AccordionSection
            title="Symbol Universe"
            badge={symbols.length > 0 ? symbols[0] : undefined}
          >
            <div className="flex flex-wrap gap-1.5 mb-2">
              {symbols.map((s) => (
                <span key={s}
                  className="app-pill items-center gap-1 px-2.5 py-1 text-xs font-mono tracking-normal">
                  {s}
                  <button type="button" onClick={() => setSymbols((prev) => prev.filter((x) => x !== s))}
                    className="text-muted-foreground hover:text-red-400 transition-colors ml-0.5">×</button>
                </span>
              ))}
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
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
              <button type="button" onClick={() => addSymbol(symbolInput)}
                className="app-button-secondary h-11 px-5">
                Add
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              First symbol is used as default for backtesting.
            </p>
          </AccordionSection>

          <AccordionSection title="Execution Settings">
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
            </div>
          </AccordionSection>

          <AccordionSection title="Risk Controls">
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

        <div className="space-y-4 lg:sticky lg:top-28 lg:self-start">
          <DiagnosticPanel report={diagnostics} loading={diagLoading} />
          <ExplainerPanel explanation={explanation} loading={explainLoading} />
        </div>
      </div>
    </div>
  );
}
