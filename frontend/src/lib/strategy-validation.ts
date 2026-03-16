import type { BuilderState } from "@/stores/builder-store";

/**
 * Validate the builder state before saving a strategy.
 * Returns a list of human-readable issues and whether the strategy can be saved.
 */
export function validateStrategy(state: BuilderState): {
  canSave: boolean;
  issues: string[];
} {
  const issues: string[] = [];

  // Name is required
  if (!state.name.trim()) {
    issues.push("Strategy name is required.");
  }

  // At least one symbol
  if (state.symbols.length === 0) {
    issues.push("Add at least one symbol.");
  }

  // At least one entry condition with indicator + operator + value
  const hasValidCondition = state.conditionGroups.some((group) =>
    group.conditions.some(
      (c) => c.indicator && c.operator && (c.value !== undefined && c.value !== ""),
    ),
  );
  if (!hasValidCondition) {
    issues.push("Add at least one entry condition with an indicator, operator, and value.");
  }

  // Stop loss > 0
  if (state.stopLoss <= 0) {
    issues.push("Stop loss must be greater than 0%.");
  }

  // Take profit > 0
  if (state.takeProfit <= 0) {
    issues.push("Take profit must be greater than 0%.");
  }

  // Position size > 0 and <= 100
  if (state.positionSize <= 0 || state.positionSize > 100) {
    issues.push("Position size must be between 0% and 100%.");
  }

  return { canSave: issues.length === 0, issues };
}
