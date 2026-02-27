"use client";

import React, { useState, useCallback, useEffect } from "react";
import { Plus, Play, Save, RotateCcw, Zap } from "lucide-react";
import { ConditionRow } from "./ConditionRow";
import { DiagnosticPanel } from "./DiagnosticPanel";
import { ExplainerPanel } from "./ExplainerPanel";
import type {
  StrategyCondition,
  Strategy,
  DiagnosticReport,
  StrategyExplanation,
  Action,
  Operator,
} from "@/types/strategy";

function generateId(): string {
  return `cond_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

function createEmptyCondition(): StrategyCondition {
  return {
    id: generateId(),
    indicator: "",
    operator: "<" as Operator,
    value: 30,
    params: {},
    action: "BUY",
  };
}

function buildLogicString(conditions: StrategyCondition[], action: Action): string {
  const parts = conditions
    .filter((c) => c.indicator)
    .map((c) => {
      const paramStr = Object.entries(c.params)
        .map(([, v]) => v)
        .join(", ");
      const ind = c.indicator.toUpperCase().replace("_", " ");
      const indWithParams = paramStr ? `${ind}(${paramStr})` : ind;
      return `${indWithParams} ${c.operator} ${c.value}`;
    });
  if (parts.length === 0) return "";
  return `IF ${parts.join(" AND ")} THEN ${action}`;
}

export function StrategyBuilder() {
  const [name, setName] = useState("My Strategy");
  const [description, setDescription] = useState("");
  const [action, setAction] = useState<Action>("BUY");
  const [conditions, setConditions] = useState<StrategyCondition[]>([
    createEmptyCondition(),
  ]);
  const [stopLoss, setStopLoss] = useState(2);
  const [takeProfit, setTakeProfit] = useState(5);
  const [positionSize, setPositionSize] = useState(10);
  const [timeframe, setTimeframe] = useState("1D");

  const [diagnostics, setDiagnostics] = useState<DiagnosticReport | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [explanation, setExplanation] = useState<StrategyExplanation | null>(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  const addCondition = useCallback(() => {
    setConditions((prev) => [...prev, createEmptyCondition()]);
  }, []);

  const removeCondition = useCallback((index: number) => {
    setConditions((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const updateCondition = useCallback(
    (index: number, updated: Partial<StrategyCondition>) => {
      setConditions((prev) =>
        prev.map((c, i) => (i === index ? { ...c, ...updated } : c))
      );
    },
    []
  );

  const resetBuilder = useCallback(() => {
    setConditions([createEmptyCondition()]);
    setDiagnostics(null);
    setExplanation(null);
    setName("My Strategy");
    setDescription("");
    setSaveStatus("idle");
  }, []);

  // Auto-run diagnostics when conditions change
  const validConditions = conditions.filter((c) => c.indicator);
  useEffect(() => {
    if (validConditions.length === 0) {
      setDiagnostics(null);
      return;
    }

    const timeout = setTimeout(async () => {
      setDiagLoading(true);
      try {
        const params: Record<string, Record<string, number>> = {};
        for (const c of validConditions) {
          params[c.indicator] = c.params;
        }
        const res = await fetch("/api/strategies/diagnose", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            conditions: validConditions.map((c) => ({
              indicator: c.indicator,
              operator: c.operator,
              value: c.value,
              params: c.params,
              action: c.action,
            })),
            parameters: params,
          }),
        });
        if (res.ok) {
          setDiagnostics(await res.json());
        }
      } catch {
        // Network error — diagnostics will show null
      } finally {
        setDiagLoading(false);
      }
    }, 500);

    return () => clearTimeout(timeout);
  }, [validConditions.map((c) => `${c.indicator}:${c.operator}:${c.value}:${JSON.stringify(c.params)}`).join("|")]);

  const runExplainer = async () => {
    const logic = buildLogicString(conditions, action);
    if (!logic) return;
    setExplainLoading(true);
    try {
      const res = await fetch("/api/explain/strategy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_logic: logic }),
      });
      if (res.ok) {
        setExplanation(await res.json());
      }
    } catch {
      // Network error
    } finally {
      setExplainLoading(false);
    }
  };

  const saveStrategy = async () => {
    setSaveStatus("saving");
    try {
      const strategy: Strategy = {
        name,
        description,
        conditions: validConditions,
        action,
        stop_loss_pct: stopLoss / 100,
        take_profit_pct: takeProfit / 100,
        position_size_pct: positionSize / 100,
        timeframe,
      };
      const res = await fetch("/api/strategies/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(strategy),
      });
      if (res.ok) {
        setSaveStatus("saved");
        setTimeout(() => setSaveStatus("idle"), 3000);
      } else {
        setSaveStatus("error");
      }
    } catch {
      setSaveStatus("error");
    }
  };

  const logicString = buildLogicString(conditions, action);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Strategy Builder</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Define entry conditions with real-time diagnostics
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={resetBuilder}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset
          </button>
          <button
            onClick={runExplainer}
            disabled={validConditions.length === 0}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-primary/30 bg-primary/5 text-sm text-primary hover:bg-primary/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Zap className="h-3.5 w-3.5" />
            Analyze
          </button>
          <button
            onClick={saveStrategy}
            disabled={validConditions.length === 0 || saveStatus === "saving"}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Save className="h-3.5 w-3.5" />
            {saveStatus === "saving"
              ? "Saving..."
              : saveStatus === "saved"
                ? "Saved"
                : "Save"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Builder */}
        <div className="lg:col-span-2 space-y-4">
          {/* Strategy name & config */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Strategy Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
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
                className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
          </div>

          {/* Action + Risk params */}
          <div className="grid grid-cols-5 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Action
              </label>
              <select
                value={action}
                onChange={(e) => setAction(e.target.value as Action)}
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <option value="BUY">BUY</option>
                <option value="SELL">SELL</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Stop Loss %
              </label>
              <input
                type="number"
                value={stopLoss}
                onChange={(e) => setStopLoss(parseFloat(e.target.value) || 0)}
                min={0.1}
                max={50}
                step={0.5}
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Take Profit %
              </label>
              <input
                type="number"
                value={takeProfit}
                onChange={(e) => setTakeProfit(parseFloat(e.target.value) || 0)}
                min={0.1}
                max={100}
                step={0.5}
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Position %
              </label>
              <input
                type="number"
                value={positionSize}
                onChange={(e) => setPositionSize(parseFloat(e.target.value) || 0)}
                min={1}
                max={100}
                step={1}
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Timeframe
              </label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className="mt-1 h-9 w-full rounded-md border bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <option value="1m">1 min</option>
                <option value="5m">5 min</option>
                <option value="15m">15 min</option>
                <option value="1H">1 hour</option>
                <option value="4H">4 hour</option>
                <option value="1D">Daily</option>
                <option value="1W">Weekly</option>
              </select>
            </div>
          </div>

          {/* Conditions */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Entry Conditions
              </h3>
              <span className="text-xs text-muted-foreground">
                {validConditions.length} active
              </span>
            </div>

            <div className="space-y-2">
              {conditions.map((condition, index) => (
                <ConditionRow
                  key={condition.id}
                  condition={condition}
                  index={index}
                  onChange={updateCondition}
                  onRemove={removeCondition}
                />
              ))}
            </div>

            <button
              onClick={addCondition}
              className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed text-sm text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-primary/5 transition-colors"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Condition
            </button>
          </div>

          {/* Logic preview */}
          {logicString && (
            <div className="rounded-lg border bg-muted/30 p-3">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
                Strategy Logic
              </div>
              <code className="text-sm font-mono text-primary break-all">
                {logicString}
              </code>
            </div>
          )}
        </div>

        {/* Right column: Diagnostics & Explainer */}
        <div className="space-y-4">
          <DiagnosticPanel report={diagnostics} loading={diagLoading} />
          <ExplainerPanel explanation={explanation} loading={explainLoading} />
        </div>
      </div>
    </div>
  );
}
