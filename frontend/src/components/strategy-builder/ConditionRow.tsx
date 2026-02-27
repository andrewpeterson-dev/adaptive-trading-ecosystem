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
  onChange: (index: number, updated: Partial<StrategyCondition>) => void;
  onRemove: (index: number) => void;
}

export function ConditionRow({
  condition,
  index,
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
    <div className="group flex items-start gap-2 p-3 rounded-lg border bg-card hover:border-primary/30 transition-colors">
      <div className="mt-2 text-muted-foreground/40 cursor-grab">
        <GripVertical className="h-4 w-4" />
      </div>

      <div className="flex-1 space-y-2">
        {/* Row 1: Indicator selector + info button */}
        <div className="flex items-center gap-2 flex-wrap">
          {index > 0 && (
            <span className="text-xs font-semibold text-primary uppercase tracking-wider px-2 py-0.5 rounded bg-primary/10">
              AND
            </span>
          )}

          <select
            value={condition.indicator}
            onChange={(e) => handleIndicatorChange(e.target.value)}
            className="h-8 rounded-md border bg-background px-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-primary/50"
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
              className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${catColor}`}
            >
              {selected.category}
            </span>
          )}

          {/* Operator */}
          <select
            value={condition.operator}
            onChange={(e) =>
              onChange(index, { operator: e.target.value as Operator })
            }
            className="h-8 rounded-md border bg-background px-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/50"
          >
            {OPERATORS.map((op) => (
              <option key={op.value} value={op.value}>
                {op.label}
              </option>
            ))}
          </select>

          {/* Value */}
          <input
            type="number"
            value={condition.value}
            onChange={(e) =>
              onChange(index, { value: parseFloat(e.target.value) || 0 })
            }
            className="h-8 w-20 rounded-md border bg-background px-2 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-primary/50"
            step="any"
          />
        </div>

        {/* Row 2: Parameter editors */}
        {selected && Object.keys(selected.parameters).length > 0 && (
          <div className="flex items-center gap-3 pl-1 flex-wrap">
            {Object.entries(selected.parameters).map(([key, param]) => (
              <div key={key} className="flex items-center gap-1.5">
                <label className="text-[11px] text-muted-foreground font-medium uppercase tracking-wider">
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
                  className="h-6 w-16 rounded border bg-muted/50 px-1.5 text-xs font-mono text-center focus:outline-none focus:ring-1 focus:ring-primary/50"
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => onRemove(index)}
        className="mt-2 p-1 rounded text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors"
        aria-label="Remove condition"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}
