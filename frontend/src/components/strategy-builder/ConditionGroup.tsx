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
    <div className="rounded-lg border border-border/50 bg-card/50 overflow-hidden">
      {/* Group header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-muted/20 border-b border-border/40">
        <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
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

      {/* Conditions */}
      <div className="p-2 space-y-2">
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
          className="w-full flex items-center justify-center gap-1 py-1.5 rounded border border-dashed border-border/40 text-xs text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-primary/5 transition-colors"
        >
          <Plus className="h-3 w-3" />
          Add Condition
        </button>
      </div>
    </div>
  );
}
