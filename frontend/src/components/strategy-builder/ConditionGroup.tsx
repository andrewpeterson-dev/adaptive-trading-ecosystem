"use client";

import React from "react";
import { Plus, X } from "lucide-react";
import { ConditionRow } from "./ConditionRow";
import type {
  ConditionGroup as ConditionGroupType,
  StrategyCondition,
} from "@/types/strategy";

interface ConditionGroupProps {
  group: ConditionGroupType;
  groupIndex: number;
  totalGroups: number;
  onAddCondition: (groupIndex: number) => void;
  onRemoveCondition: (groupIndex: number, condIndex: number) => void;
  onUpdateCondition: (
    groupIndex: number,
    condIndex: number,
    updated: Partial<StrategyCondition>
  ) => void;
  onRemoveGroup: (groupIndex: number) => void;
}

export function ConditionGroup({
  group,
  groupIndex,
  totalGroups,
  onAddCondition,
  onRemoveCondition,
  onUpdateCondition,
  onRemoveGroup,
}: ConditionGroupProps) {
  const label = String.fromCharCode(65 + groupIndex); // A, B, C…
  const canRemoveGroup = totalGroups > 1;
  const isLastConditionInLastGroup =
    group.conditions.length === 1 && totalGroups === 1;

  return (
    <div className="app-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-border/50 bg-slate-950/[0.03] px-4 py-3 dark:bg-white/[0.03]">
        <span className="app-label">
          Group {label}
        </span>
        <button
          type="button"
          onClick={() => onRemoveGroup(groupIndex)}
          disabled={!canRemoveGroup}
          title={canRemoveGroup ? "Remove group" : "Need at least one group"}
          className="p-0.5 rounded text-muted-foreground/40 hover:text-red-400 hover:bg-red-400/10 transition-colors disabled:opacity-0 disabled:cursor-default"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="space-y-3 p-3">
        {group.conditions.map((condition, condIndex) => (
          <React.Fragment key={condition.id}>
            {condIndex > 0 && (
              <div className="flex items-center gap-2 px-1">
                <div className="flex-1 h-px bg-border/30" />
                <span className="text-[9px] font-bold uppercase tracking-widest text-muted-foreground/50">
                  AND
                </span>
                <div className="flex-1 h-px bg-border/30" />
              </div>
            )}
            <ConditionRow
              condition={condition}
              index={condIndex}
              isOnly={isLastConditionInLastGroup}
              onChange={(_idx, updated) =>
                onUpdateCondition(groupIndex, condIndex, updated)
              }
              onRemove={() => onRemoveCondition(groupIndex, condIndex)}
            />
          </React.Fragment>
        ))}

        <button
          type="button"
          onClick={() => onAddCondition(groupIndex)}
          className="app-inset flex w-full items-center justify-center gap-1 py-3 text-xs font-medium text-muted-foreground hover:text-foreground"
        >
          <Plus className="h-3 w-3" />
          Add Condition
        </button>
      </div>
    </div>
  );
}
