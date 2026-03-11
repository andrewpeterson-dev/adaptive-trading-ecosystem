"use client";

import React from "react";
import { Trash2, GripVertical } from "lucide-react";
import { IndicatorInfoButton } from "@/components/indicators/IndicatorInfoButton";
import { getAllIndicators } from "@/lib/indicatorRegistry";
import type { IndicatorId, IndicatorMetadata } from "@/types/indicators";
import type { StrategyCondition, Operator } from "@/types/strategy";
import { CATEGORY_COLORS } from "@/types/indicators";

const OPERATORS: { value: Operator; label: string }[] = [
  { value: ">", label: ">" },
  { value: "<", label: "<" },
  { value: ">=", label: ">=" },
  { value: "<=", label: "<=" },
  { value: "==", label: "=" },
  { value: "crosses_above", label: "Crosses Above" },
  { value: "crosses_below", label: "Crosses Below" },
];

interface ConditionRowProps {
  condition: StrategyCondition;
  index: number;
  isOnly: boolean;
  onChange: (index: number, updated: Partial<StrategyCondition>) => void;
  onRemove: (index: number) => void;
}

export function ConditionRow({
  condition,
  index,
  isOnly,
  onChange,
  onRemove,
}: ConditionRowProps) {
  const allIndicators = getAllIndicators();
  const selected = allIndicators.find(
    (m) => m.id === condition.indicator
  );

  const handleIndicatorChange = (indicatorId: string) => {
    const meta = allIndicators.find((m) => m.id === indicatorId);
    const defaultParams: Record<string, number> = {};
    if (meta) {
      for (const [key, param] of Object.entries(meta.parameters)) {
        defaultParams[key] = param.default;
      }
    }
    onChange(index, { indicator: indicatorId, params: defaultParams });
  };

  const handleParamChange = (paramName: string, value: number) => {
    onChange(index, {
      params: { ...condition.params, [paramName]: value },
    });
  };

  const catColor = selected ? CATEGORY_COLORS[selected.category] ?? "" : "";

  return (
    <div className="app-inset group flex flex-col gap-3 p-3 sm:flex-row sm:items-start">
      <div className="mt-2 text-muted-foreground/40 cursor-grab">
        <GripVertical className="h-4 w-4" />
      </div>

      <div className="flex-1 space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          {index > 0 && (
            <span className="rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
              AND
            </span>
          )}

          <select
            value={condition.indicator}
            onChange={(e) => handleIndicatorChange(e.target.value)}
            className="app-select h-10 min-w-[220px] rounded-2xl px-3 py-0 text-sm font-medium"
          >
            <option value="">Select indicator...</option>
            {allIndicators.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
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

          {condition.indicator && (
            <>
              <select
                value={condition.operator}
                onChange={(e) =>
                  onChange(index, { operator: e.target.value as Operator })
                }
                aria-label="Comparison operator"
                className="app-select h-10 rounded-2xl px-3 py-0 text-sm font-mono"
              >
                {OPERATORS.map((op) => (
                  <option key={op.value} value={op.value}>
                    {op.label}
                  </option>
                ))}
              </select>

              <input
                type="number"
                value={condition.value}
                  onChange={(e) =>
                    onChange(index, { value: parseFloat(e.target.value) || 0 })
                  }
                  aria-label="Threshold value"
                className="app-input h-10 w-24 rounded-2xl px-3 py-0 text-right font-mono"
                step="any"
              />
            </>
          )}
        </div>

        {selected && Object.keys(selected.parameters).length > 0 && (
          <div className="flex items-center gap-3 pl-1 flex-wrap">
            {Object.entries(selected.parameters).map(([key, param]) => (
              <div key={key} className="flex items-center gap-1.5">
                <label className="app-label tracking-[0.14em]">
                  {key}
                </label>
                <input
                  type="number"
                  value={condition.params[key] ?? param.default}
                  min={param.min}
                  max={param.max}
                  onChange={(e) =>
                    handleParamChange(key, parseFloat(e.target.value) || param.default)
                  }
                  className="app-input h-9 w-20 rounded-xl px-2 py-0 text-center text-xs font-mono"
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => onRemove(index)}
        disabled={isOnly}
        title={isOnly ? "At least one condition is required" : "Remove condition"}
        className="self-end rounded-xl p-2 text-muted-foreground/40 transition-colors hover:bg-red-400/10 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-20 disabled:hover:bg-transparent disabled:hover:text-muted-foreground/40 sm:self-start"
        aria-label="Remove condition"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}
