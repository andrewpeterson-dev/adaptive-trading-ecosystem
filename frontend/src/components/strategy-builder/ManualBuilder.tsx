"use client";

import React, { useState } from "react";
import {
  Settings,
  TrendingUp,
  TrendingDown,
  Shield,
  Zap,
  Plus,
  X,
} from "lucide-react";
import { AccordionSection } from "./AccordionSection";
import { ConditionGroup as ConditionGroupComponent } from "./ConditionGroup";
import { useBuilderStore } from "@/stores/builder-store";
import type {
  ConditionGroup,
  LogicalJoiner,
  StrategyCondition,
  Action,
} from "@/types/strategy";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let conditionIdCounter = 0;
function nextConditionId(): string {
  conditionIdCounter += 1;
  return `c_${Date.now()}_${conditionIdCounter}`;
}

const TIMEFRAMES = ["1m", "5m", "15m", "1H", "4H", "1D", "1W"] as const;

const BACKTEST_PERIODS = [
  { value: "1M", label: "1 Month" },
  { value: "3M", label: "3 Months" },
  { value: "6M", label: "6 Months" },
  { value: "1Y", label: "1 Year" },
  { value: "2Y", label: "2 Years" },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ManualBuilder() {
  const store = useBuilderStore();
  const [symbolInput, setSymbolInput] = useState("");

  // ---- Symbol helpers ----
  const addSymbol = (raw: string) => {
    const sym = raw.trim().toUpperCase();
    if (!sym || store.symbols.includes(sym)) {
      setSymbolInput("");
      return;
    }
    store.setField("symbols", [...store.symbols, sym]);
    setSymbolInput("");
  };

  const removeSymbol = (sym: string) => {
    store.setField(
      "symbols",
      store.symbols.filter((s) => s !== sym),
    );
  };

  // ---- Entry condition group CRUD ----
  const addEntryGroup = () => {
    const newId = String.fromCharCode(65 + store.conditionGroups.length);
    const newGroup: ConditionGroup = {
      id: newId,
      conditions: [
        {
          id: nextConditionId(),
          indicator: "",
          operator: ">",
          value: 0,
          params: {},
          action: store.action,
        },
      ],
      joiner: "OR",
    };
    store.setField("conditionGroups", [...store.conditionGroups, newGroup]);
  };

  const removeEntryGroup = (groupIndex: number) => {
    const updated = store.conditionGroups.filter((_, i) => i !== groupIndex);
    store.setField("conditionGroups", updated);
  };

  const addEntryCondition = (groupIndex: number) => {
    const updated = store.conditionGroups.map((g, i) => {
      if (i !== groupIndex) return g;
      return {
        ...g,
        conditions: [
          ...g.conditions,
          {
            id: nextConditionId(),
            indicator: "",
            operator: ">" as const,
            value: 0,
            params: {},
            action: store.action,
          },
        ],
      };
    });
    store.setField("conditionGroups", updated);
  };

  const removeEntryCondition = (groupIndex: number, condIndex: number) => {
    const updated = store.conditionGroups.map((g, i) => {
      if (i !== groupIndex) return g;
      return {
        ...g,
        conditions: g.conditions.filter((_, ci) => ci !== condIndex),
      };
    });
    store.setField("conditionGroups", updated);
  };

  const updateEntryCondition = (
    groupIndex: number,
    condIndex: number,
    patch: Partial<StrategyCondition>,
  ) => {
    const updated = store.conditionGroups.map((g, i) => {
      if (i !== groupIndex) return g;
      return {
        ...g,
        conditions: g.conditions.map((c, ci) =>
          ci !== condIndex ? c : { ...c, ...patch },
        ),
      };
    });
    store.setField("conditionGroups", updated);
  };

  // ---- Exit condition group CRUD ----
  const addExitGroup = () => {
    const newId = String.fromCharCode(65 + store.exitConditionGroups.length);
    const newGroup: ConditionGroup = {
      id: newId,
      conditions: [
        {
          id: nextConditionId(),
          indicator: "",
          operator: ">",
          value: 0,
          params: {},
          action: store.action,
        },
      ],
      joiner: "OR",
    };
    store.setField("exitConditionGroups", [
      ...store.exitConditionGroups,
      newGroup,
    ]);
  };

  const removeExitGroup = (groupIndex: number) => {
    const updated = store.exitConditionGroups.filter(
      (_, i) => i !== groupIndex,
    );
    store.setField("exitConditionGroups", updated);
  };

  const addExitCondition = (groupIndex: number) => {
    const updated = store.exitConditionGroups.map((g, i) => {
      if (i !== groupIndex) return g;
      return {
        ...g,
        conditions: [
          ...g.conditions,
          {
            id: nextConditionId(),
            indicator: "",
            operator: ">" as const,
            value: 0,
            params: {},
            action: store.action,
          },
        ],
      };
    });
    store.setField("exitConditionGroups", updated);
  };

  const removeExitCondition = (groupIndex: number, condIndex: number) => {
    const updated = store.exitConditionGroups.map((g, i) => {
      if (i !== groupIndex) return g;
      return {
        ...g,
        conditions: g.conditions.filter((_, ci) => ci !== condIndex),
      };
    });
    store.setField("exitConditionGroups", updated);
  };

  const updateExitCondition = (
    groupIndex: number,
    condIndex: number,
    patch: Partial<StrategyCondition>,
  ) => {
    const updated = store.exitConditionGroups.map((g, i) => {
      if (i !== groupIndex) return g;
      return {
        ...g,
        conditions: g.conditions.map((c, ci) =>
          ci !== condIndex ? c : { ...c, ...patch },
        ),
      };
    });
    store.setField("exitConditionGroups", updated);
  };

  // ---- Derived counts ----
  const entryCount = store.conditionGroups.reduce(
    (sum, g) => sum + g.conditions.filter((c) => c.indicator).length,
    0,
  );
  const exitCount = store.exitConditionGroups.reduce(
    (sum, g) => sum + g.conditions.filter((c) => c.indicator).length,
    0,
  );

  // ---- Render ----
  return (
    <div className="overflow-y-auto h-full p-4 space-y-4">
      {/* ================================================================ */}
      {/* 1. Basics                                                        */}
      {/* ================================================================ */}
      <AccordionSection
        title="Basics"
        defaultOpen
        accent="blue"
        icon={<Settings className="h-3.5 w-3.5" />}
        subtitle="Name, direction, and universe"
      >
        {/* Name */}
        <div>
          <label className="app-label">Strategy Name</label>
          <input
            type="text"
            value={store.name}
            onChange={(e) => store.setField("name", e.target.value)}
            placeholder="e.g. RSI Mean Reversion"
            className="app-input mt-2"
          />
        </div>

        {/* Description */}
        <div>
          <label className="app-label">Description</label>
          <textarea
            value={store.description}
            onChange={(e) => store.setField("description", e.target.value)}
            placeholder="Describe the strategy thesis and why the edge should persist."
            rows={2}
            className="app-input mt-2 resize-y"
          />
        </div>

        {/* Action toggle */}
        <div>
          <label className="app-label">Action</label>
          <div className="app-segmented mt-2">
            <button
              type="button"
              className={cn(
                "app-segment",
                store.action === "BUY" && "app-toggle-active",
              )}
              onClick={() => store.setField("action", "BUY" as Action)}
            >
              BUY
            </button>
            <button
              type="button"
              className={cn(
                "app-segment",
                store.action === "SELL" && "app-toggle-active",
              )}
              onClick={() => store.setField("action", "SELL" as Action)}
            >
              SELL
            </button>
          </div>
        </div>

        {/* Timeframe */}
        <div>
          <label className="app-label">Timeframe</label>
          <select
            value={store.timeframe}
            onChange={(e) => store.setField("timeframe", e.target.value)}
            className="app-select mt-2 text-sm"
          >
            {TIMEFRAMES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        {/* Symbols */}
        <div>
          <label className="app-label">Symbols</label>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {store.symbols.map((symbol, idx) => (
              <span
                key={symbol}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-mono font-semibold tracking-wide",
                  idx === 0
                    ? "border-primary/30 bg-primary/10 text-primary"
                    : "border-border/60 bg-muted/40 text-foreground",
                )}
              >
                {symbol}
                <button
                  type="button"
                  onClick={() => removeSymbol(symbol)}
                  className="ml-0.5 text-muted-foreground transition-colors hover:text-red-400"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
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
      </AccordionSection>

      {/* ================================================================ */}
      {/* 2. Entry Conditions                                              */}
      {/* ================================================================ */}
      <AccordionSection
        title="Entry Conditions"
        defaultOpen
        accent="green"
        icon={<TrendingUp className="h-3.5 w-3.5" />}
        subtitle="When to open a position"
        badge={entryCount > 0 ? `${entryCount} active` : undefined}
      >
        {store.conditionGroups.map((group, gi) => (
          <React.Fragment key={group.id}>
            {gi > 0 && (
              <div className="flex items-center justify-center gap-2 px-1">
                <div className="h-px flex-1 bg-border/30" />
                <span className="rounded-full border border-border/60 bg-muted/30 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  OR
                </span>
                <div className="h-px flex-1 bg-border/30" />
              </div>
            )}
            <div>
              <p className="app-label mb-2 text-xs text-muted-foreground">
                Entry Branch {String.fromCharCode(65 + gi)}
              </p>
              <ConditionGroupComponent
                group={group}
                groupIndex={gi}
                totalGroups={store.conditionGroups.length}
                onAddCondition={addEntryCondition}
                onRemoveCondition={removeEntryCondition}
                onUpdateCondition={updateEntryCondition}
                onRemoveGroup={removeEntryGroup}
              />
            </div>
          </React.Fragment>
        ))}

        <button
          type="button"
          onClick={addEntryGroup}
          className="app-inset flex w-full items-center justify-center gap-1.5 py-4 text-sm text-emerald-400/70 hover:text-emerald-400 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Entry Branch
        </button>
      </AccordionSection>

      {/* ================================================================ */}
      {/* 3. Exit Conditions                                               */}
      {/* ================================================================ */}
      <AccordionSection
        title="Exit Conditions"
        defaultOpen
        accent="red"
        icon={<TrendingDown className="h-3.5 w-3.5" />}
        subtitle="When to close a position"
        badge={exitCount > 0 ? `${exitCount} active` : undefined}
      >
        {store.exitConditionGroups.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No exit condition groups yet. Add one to define indicator-based
            exits.
          </p>
        ) : (
          store.exitConditionGroups.map((group, gi) => (
            <React.Fragment key={group.id}>
              {gi > 0 && (
                <div className="flex items-center justify-center gap-2 px-1">
                  <div className="h-px flex-1 bg-border/30" />
                  <span className="rounded-full border border-border/60 bg-muted/30 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    OR
                  </span>
                  <div className="h-px flex-1 bg-border/30" />
                </div>
              )}
              <div>
                <p className="app-label mb-2 text-xs text-muted-foreground">
                  Exit Branch {String.fromCharCode(65 + gi)}
                </p>
                <ConditionGroupComponent
                  group={group}
                  groupIndex={gi}
                  totalGroups={store.exitConditionGroups.length}
                  onAddCondition={addExitCondition}
                  onRemoveCondition={removeExitCondition}
                  onUpdateCondition={updateExitCondition}
                  onRemoveGroup={removeExitGroup}
                />
              </div>
            </React.Fragment>
          ))
        )}

        <button
          type="button"
          onClick={addExitGroup}
          className="app-inset flex w-full items-center justify-center gap-1.5 py-4 text-sm text-red-400/70 hover:text-red-400 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Add Exit Branch
        </button>
      </AccordionSection>

      {/* ================================================================ */}
      {/* 4. Risk Controls                                                 */}
      {/* ================================================================ */}
      <AccordionSection
        title="Risk Controls"
        accent="orange"
        icon={<Shield className="h-3.5 w-3.5" />}
        subtitle="Position limits and circuit breakers"
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="app-label">Stop Loss %</label>
            <input
              type="number"
              value={store.stopLoss}
              onChange={(e) =>
                store.setField("stopLoss", parseFloat(e.target.value) || 0)
              }
              min={0.1}
              max={50}
              step={0.5}
              className="app-input mt-2 font-mono text-right"
            />
          </div>
          <div>
            <label className="app-label">Take Profit %</label>
            <input
              type="number"
              value={store.takeProfit}
              onChange={(e) =>
                store.setField("takeProfit", parseFloat(e.target.value) || 0)
              }
              min={0.1}
              max={100}
              step={0.5}
              className="app-input mt-2 font-mono text-right"
            />
          </div>
          <div>
            <label className="app-label">Position Size %</label>
            <input
              type="number"
              value={store.positionSize}
              onChange={(e) =>
                store.setField("positionSize", parseFloat(e.target.value) || 0)
              }
              min={0}
              max={100}
              step={1}
              className="app-input mt-2 font-mono text-right"
            />
          </div>
          <div>
            <label className="app-label">Max Trades / Day</label>
            <input
              type="number"
              value={store.maxTradesPerDay}
              onChange={(e) =>
                store.setField(
                  "maxTradesPerDay",
                  parseInt(e.target.value) || 0,
                )
              }
              min={0}
              max={100}
              className="app-input mt-2 font-mono text-right"
            />
            <p className="text-[10px] text-muted-foreground mt-0.5">
              0 = unlimited
            </p>
          </div>
        </div>

        {/* Trailing stop */}
        <div className="space-y-2">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={store.trailingStopEnabled}
              onChange={(e) =>
                store.setField("trailingStopEnabled", e.target.checked)
              }
              className="rounded border-border/50"
            />
            <span className="app-label">Trailing Stop</span>
          </label>
          {store.trailingStopEnabled && (
            <input
              type="number"
              value={store.trailingStop}
              onChange={(e) =>
                store.setField(
                  "trailingStop",
                  parseFloat(e.target.value) || 0,
                )
              }
              min={0.1}
              max={50}
              step={0.5}
              placeholder="Trailing stop %"
              className="app-input h-10 w-full max-w-[10rem] font-mono text-right"
            />
          )}
        </div>
      </AccordionSection>

      {/* ================================================================ */}
      {/* 5. Execution                                                     */}
      {/* ================================================================ */}
      <AccordionSection
        title="Execution"
        accent="slate"
        icon={<Zap className="h-3.5 w-3.5" />}
        subtitle="Order routing and backtest config"
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="app-label">Order Type</label>
            <select
              value={store.orderType}
              onChange={(e) => store.setField("orderType", e.target.value)}
              className="app-select mt-2 text-sm"
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
              <option value="stop">Stop</option>
            </select>
          </div>
          <div>
            <label className="app-label">Backtest Period</label>
            <select
              value={store.backtestPeriod}
              onChange={(e) => store.setField("backtestPeriod", e.target.value)}
              className="app-select mt-2 text-sm"
            >
              {BACKTEST_PERIODS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="app-label">Commission %</label>
            <input
              type="number"
              value={store.commissionPct}
              onChange={(e) =>
                store.setField(
                  "commissionPct",
                  parseFloat(e.target.value) || 0,
                )
              }
              min={0}
              max={5}
              step={0.01}
              className="app-input mt-2 font-mono text-right"
            />
          </div>
          <div>
            <label className="app-label">Slippage %</label>
            <input
              type="number"
              value={store.slippagePct}
              onChange={(e) =>
                store.setField(
                  "slippagePct",
                  parseFloat(e.target.value) || 0,
                )
              }
              min={0}
              max={5}
              step={0.01}
              className="app-input mt-2 font-mono text-right"
            />
          </div>
        </div>
      </AccordionSection>
    </div>
  );
}
