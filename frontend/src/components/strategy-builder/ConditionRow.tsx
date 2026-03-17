"use client";

import React, { useMemo } from "react";
import { Trash2 } from "lucide-react";
import { IndicatorInfoButton } from "@/components/indicators/IndicatorInfoButton";
import { getAllIndicators } from "@/lib/indicatorRegistry";
import type { IndicatorId } from "@/types/indicators";
import type { StrategyCondition, Operator } from "@/types/strategy";
import { CATEGORY_COLORS } from "@/types/indicators";

const OPERATORS: { value: Operator; label: string }[] = [
  { value: ">", label: "Greater Than" },
  { value: "<", label: "Less Than" },
  { value: ">=", label: "At / Above" },
  { value: "<=", label: "At / Below" },
  { value: "==", label: "Equals" },
  { value: "crosses_above", label: "Crosses Above" },
  { value: "crosses_below", label: "Crosses Below" },
];

const COMPARISON_TARGETS = [
  { value: "__value__", label: "Numeric Threshold" },
  { value: "price", label: "Price" },
  { value: "sma", label: "SMA" },
  { value: "ema", label: "EMA" },
  { value: "vwap", label: "VWAP" },
  { value: "signal_line", label: "Signal Line" },
];

interface ConditionRowProps {
  condition: StrategyCondition;
  index: number;
  isOnly: boolean;
  onChange: (index: number, updated: Partial<StrategyCondition>) => void;
  onRemove: (index: number) => void;
}

function toReadableSummary(condition: StrategyCondition): string {
  if (!condition.indicator) {
    return "Choose an indicator to define the entry rule.";
  }

  const indicatorLabel = condition.indicator.toUpperCase().replace(/_/g, " ");
  const params = Object.values(condition.params);
  const paramLabel = params.length > 0 ? `(${params.join(", ")})` : "";
  const operatorLabel =
    OPERATORS.find((operator) => operator.value === condition.operator)?.label ??
    condition.operator;
  const comparisonLabel = condition.compare_to
    ? condition.compare_to.replace(/_/g, " ").toUpperCase()
    : String(condition.value);

  return `${indicatorLabel}${paramLabel} ${operatorLabel.toUpperCase()} ${comparisonLabel}`;
}

export function ConditionRow({
  condition,
  index,
  isOnly,
  onChange,
  onRemove,
}: ConditionRowProps) {
  const allIndicators = useMemo(() => getAllIndicators(), []);
  const selected = allIndicators.find((metadata) => metadata.id === condition.indicator);
  const catColor = selected ? CATEGORY_COLORS[selected.category] ?? "" : "";
  const comparisonTarget = condition.compare_to ?? "__value__";
  const usesReferenceComparison = comparisonTarget !== "__value__";
  const thresholdLabel =
    condition.operator === "crosses_above" || condition.operator === "crosses_below"
      ? "3. Crossover"
      : "3. Threshold";

  const handleIndicatorChange = (indicatorId: string) => {
    const meta = allIndicators.find((indicator) => indicator.id === indicatorId);
    const defaultParams: Record<string, number> = {};
    if (meta) {
      for (const [key, param] of Object.entries(meta.parameters)) {
        defaultParams[key] = param.default;
      }
    }

    onChange(index, {
      indicator: indicatorId,
      params: defaultParams,
      compare_to: undefined,
      value: 30,
    });
  };

  const handleParamChange = (paramName: string, value: number) => {
    onChange(index, {
      params: { ...condition.params, [paramName]: value },
    });
  };

  return (
    <div className="app-inset group flex flex-col gap-4 rounded-[24px] p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted/30 mt-8">
          <span className="text-[10px] font-bold text-muted-foreground">{index + 1}</span>
        </div>

        <div className="flex-1 space-y-4">
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)]">
            <div>
              <label className="app-label">1. Signal</label>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                <select
                  value={condition.indicator}
                  onChange={(event) => handleIndicatorChange(event.target.value)}
                  className="app-select h-11 w-full rounded-2xl px-3 py-0 text-sm font-medium sm:min-w-[220px] sm:w-auto"
                >
                  <option value="">Select indicator...</option>
                  {allIndicators.map((indicator) => (
                    <option key={indicator.id} value={indicator.id}>
                      {indicator.name}
                    </option>
                  ))}
                </select>

                {condition.indicator && (
                  <IndicatorInfoButton
                    indicator={condition.indicator as IndicatorId}
                    size="sm"
                  />
                )}

                {selected && (
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${catColor}`}
                  >
                    {selected.category}
                  </span>
                )}
              </div>
              {!condition.indicator && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Start with the indicator Cerberus or the strategy thesis depends on.
                </p>
              )}
            </div>

            <div>
              <label className="app-label">2. Trigger</label>
              <select
                value={condition.operator}
                onChange={(event) =>
                  onChange(index, { operator: event.target.value as Operator })
                }
                aria-label="Comparison operator"
                disabled={!condition.indicator}
                className="app-select mt-2 h-11 rounded-2xl px-3 py-0 text-sm disabled:opacity-50"
              >
                {OPERATORS.map((operator) => (
                  <option key={operator.value} value={operator.value}>
                    {operator.label}
                  </option>
                ))}
              </select>
              <p className="mt-2 text-xs text-muted-foreground">
                Pick whether the signal is a threshold check or a crossover event.
              </p>
            </div>

            <div>
              <label className="app-label">{thresholdLabel}</label>
              <div className="mt-2 space-y-2">
                <select
                  value={comparisonTarget}
                  onChange={(event) => {
                    const nextValue = event.target.value;
                    onChange(index, {
                      compare_to: nextValue === "__value__" ? undefined : nextValue,
                    });
                  }}
                  disabled={!condition.indicator}
                  className="app-select h-11 w-full rounded-2xl px-3 py-0 text-sm disabled:opacity-50"
                >
                  {COMPARISON_TARGETS.map((target) => (
                    <option key={target.value} value={target.value}>
                      {target.label}
                    </option>
                  ))}
                </select>

                {usesReferenceComparison ? (
                  <div className="rounded-2xl border border-border/60 bg-background/60 px-3 py-2 text-xs text-muted-foreground">
                    This rule will compare against{" "}
                    <span className="font-semibold text-foreground">
                      {comparisonTarget.replace(/_/g, " ")}
                    </span>
                    .
                  </div>
                ) : (
                  <input
                    type="number"
                    value={condition.value}
                    onChange={(event) =>
                      onChange(index, {
                        value: parseFloat(event.target.value) || 0,
                      })
                    }
                    aria-label="Threshold value"
                    disabled={!condition.indicator}
                    className="app-input h-11 w-full rounded-2xl px-3 py-0 text-right font-mono disabled:opacity-50"
                    step="any"
                  />
                )}
              </div>
            </div>
          </div>

          {selected && Object.keys(selected.parameters).length > 0 && (
            <div>
              <p className="app-label">Indicator Parameters</p>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                {Object.entries(selected.parameters).map(([key, param]) => (
                  <div key={key} className="flex items-center gap-1.5">
                    <label className="app-label tracking-[0.14em]">{key}</label>
                    <input
                      type="number"
                      value={condition.params[key] ?? param.default}
                      min={param.min}
                      max={param.max}
                      onChange={(event) =>
                        handleParamChange(
                          key,
                          parseFloat(event.target.value) || param.default
                        )
                      }
                      className="app-input h-9 w-20 rounded-xl px-2 py-0 text-center text-xs font-mono"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-[20px] border border-border/60 bg-background/60 p-3">
            <p className="app-label">Readable Rule</p>
            <p className="mt-2 text-sm text-foreground">
              {toReadableSummary(condition)}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => onRemove(index)}
          disabled={isOnly}
          title={isOnly ? "At least one condition is required" : "Remove condition"}
          className="rounded-xl p-2 text-muted-foreground/40 transition-colors hover:bg-red-400/10 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-20 disabled:hover:bg-transparent disabled:hover:text-muted-foreground/40"
          aria-label="Remove condition"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
