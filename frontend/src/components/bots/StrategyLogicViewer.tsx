"use client";

import { GitBranch, MoveRight } from "lucide-react";

import type { BotDetail } from "@/lib/cerberus-api";
import {
  describeCondition,
  formatConditionParams,
  getBotConfig,
  getConditionGroups,
  getExitConditions,
  humanizeLabel,
} from "@/lib/bot-visualization";

function RuleNode({
  title,
  params,
  tone,
}: {
  title: string;
  params: string[];
  tone: "entry" | "exit";
}) {
  return (
    <div
      className={`rounded-[20px] border px-4 py-4 ${
        tone === "entry"
          ? "border-emerald-400/20 bg-emerald-400/5"
          : "border-sky-400/20 bg-sky-400/5"
      }`}
    >
      <div className="text-sm font-semibold text-foreground">{title}</div>
      {params.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {params.map((param) => (
            <span
              key={param}
              className="rounded-full border border-white/10 bg-background/70 px-2.5 py-1 text-[11px] text-muted-foreground"
            >
              {param}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function StrategyLogicViewer({ detail }: { detail: BotDetail }) {
  const config = getBotConfig(detail);
  const entryGroups = getConditionGroups(config);
  const exitConditions = getExitConditions(config);
  const derivedExitRules = [
    typeof config.stop_loss_pct === "number" && config.stop_loss_pct > 0
      ? `Stop loss at ${(config.stop_loss_pct * 100).toFixed(1)}%`
      : null,
    typeof config.take_profit_pct === "number" && config.take_profit_pct > 0
      ? `Take profit at ${(config.take_profit_pct * 100).toFixed(1)}%`
      : null,
    typeof config.trailing_stop_pct === "number" && config.trailing_stop_pct > 0
      ? `Trailing stop at ${(config.trailing_stop_pct * 100).toFixed(1)}%`
      : null,
    typeof config.exit_after_bars === "number" && config.exit_after_bars > 0
      ? `Exit after ${config.exit_after_bars} bars`
      : null,
  ].filter((rule): rule is string => Boolean(rule));

  return (
    <section className="app-panel p-5 sm:p-6">
      <div className="mb-5 flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-fuchsia-400" />
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Strategy Logic Visualizer
          </div>
          <h3 className="mt-1 text-lg font-semibold text-foreground">Signal tree and rule flow</h3>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div>
          <div className="mb-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Entry Conditions
          </div>
          {entryGroups.length === 0 ? (
            <div className="rounded-[20px] border border-border/60 bg-muted/15 px-4 py-5 text-sm text-muted-foreground">
              No structured entry rules were stored for this bot version.
            </div>
          ) : (
            <div className="space-y-4">
              {entryGroups.map((group, groupIndex) => (
                <div key={group.id ?? `group-${groupIndex}`} className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-emerald-400/20 bg-emerald-400/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-400">
                      {group.label ?? `Group ${String.fromCharCode(65 + groupIndex)}`}
                    </span>
                    <span className="text-xs text-muted-foreground">All conditions below must pass.</span>
                  </div>
                  <div className="space-y-3 rounded-[22px] border border-border/60 bg-muted/10 p-4">
                    {(group.conditions ?? []).map((condition, conditionIndex) => (
                      <div key={`${group.id ?? groupIndex}-${conditionIndex}`} className="space-y-3">
                        {conditionIndex > 0 && (
                          <div className="flex items-center gap-3">
                            <div className="h-px flex-1 bg-border/60" />
                            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                              AND
                            </span>
                            <div className="h-px flex-1 bg-border/60" />
                          </div>
                        )}
                        <RuleNode
                          title={describeCondition(condition)}
                          params={formatConditionParams(condition)}
                          tone="entry"
                        />
                      </div>
                    ))}
                  </div>
                  {groupIndex < entryGroups.length - 1 && (
                    <div className="flex items-center justify-center gap-2 text-muted-foreground">
                      <MoveRight className="h-4 w-4" />
                      <span className="text-[10px] font-semibold uppercase tracking-[0.18em]">OR</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="mb-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Exit Conditions
          </div>
          {exitConditions.length === 0 && derivedExitRules.length === 0 ? (
            <div className="rounded-[20px] border border-border/60 bg-muted/15 px-4 py-5 text-sm text-muted-foreground">
              No explicit exit logic was stored. The bot may be relying on runtime trade management.
            </div>
          ) : (
            <div className="space-y-3 rounded-[22px] border border-border/60 bg-muted/10 p-4">
              {exitConditions.map((condition, index) => (
                <div key={`exit-${index}`} className="space-y-3">
                  {index > 0 && (
                    <div className="flex items-center gap-3">
                      <div className="h-px flex-1 bg-border/60" />
                      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        {humanizeLabel(condition.logic ?? "or")}
                      </span>
                      <div className="h-px flex-1 bg-border/60" />
                    </div>
                  )}
                  <RuleNode
                    title={describeCondition(condition)}
                    params={formatConditionParams(condition)}
                    tone="exit"
                  />
                </div>
              ))}

              {derivedExitRules.length > 0 && (
                <div className="grid gap-3 pt-2">
                  {derivedExitRules.map((rule) => (
                    <RuleNode key={rule} title={rule} params={[]} tone="exit" />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
