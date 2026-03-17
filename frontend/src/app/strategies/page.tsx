"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Trash2,
  Pencil,
  Play,
  Copy,
  Rocket,
  Brain,
  Loader2,
  AlertTriangle,
  Layers,
  MoreHorizontal,
} from "lucide-react";
import { CardSkeleton } from "@/components/ui/skeleton";
import { apiFetch } from "@/lib/api/client";
import { deployBotFromStrategy } from "@/lib/cerberus-api";
import {
  DeployConfigModal,
  type DeployConfig,
} from "@/components/bots/DeployConfigModal";
import type { StrategyRecord } from "@/types/strategy";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 70 ? "text-emerald-400" : score >= 40 ? "text-amber-400" : "text-red-400";
  const strokeColor = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";
  const circumference = 2 * Math.PI * 14;
  const offset = circumference - (score / 100) * circumference;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn("relative inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]", color,
          score >= 70 ? "border-emerald-500/25 bg-emerald-500/12" : score >= 40 ? "border-amber-500/25 bg-amber-500/12" : "border-red-500/25 bg-red-500/12"
        )}>
          <svg width="20" height="20" viewBox="0 0 32 32" className="score-ring">
            <circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" strokeWidth="2.5" opacity="0.2" />
            <circle cx="16" cy="16" r="14" fill="none" stroke={strokeColor} strokeWidth="2.5"
              strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" />
          </svg>
          {score}
        </span>
      </TooltipTrigger>
      <TooltipContent>Strategy quality score based on backtest consistency, condition clarity, and risk controls</TooltipContent>
    </Tooltip>
  );
}

function TokenizedConditions({ summary }: { summary: string }) {
  if (!summary) return <span className="text-muted-foreground">No conditions defined yet.</span>;
  const tokens = summary.split(/\s+/);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {tokens.map((token, i) => {
        if (/^(AND|OR)$/i.test(token)) return <span key={i} className="text-xs text-muted-foreground font-medium">{token}</span>;
        if (/^[A-Z_]{2,}/.test(token)) return <span key={i} className="rounded-md bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 text-[11px] font-semibold text-blue-400 font-mono">{token}</span>;
        if (/^[<>=!]/.test(token)) return <span key={i} className="text-xs text-muted-foreground">{token}</span>;
        if (/^\d/.test(token)) return <span key={i} className="text-[11px] font-mono text-foreground">{token}</span>;
        return <span key={i} className="text-xs text-muted-foreground">{token}</span>;
      })}
    </div>
  );
}

function relativeTime(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 0) return "just now";
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function conditionCount(strategy: StrategyRecord): number {
  if (strategy.condition_groups?.length) {
    return strategy.condition_groups.reduce(
      (sum, group) => sum + (group.conditions?.length ?? 0),
      0
    );
  }
  return strategy.conditions?.length ?? 0;
}

function conditionSummary(strategy: StrategyRecord): string {
  if (strategy.condition_groups?.length) {
    return strategy.condition_groups
      .map((group) =>
        group.conditions
          .map(
            (condition) =>
              `${condition.indicator.toUpperCase()} ${condition.operator} ${condition.value}`
          )
          .join(" AND ")
      )
      .join(" OR ");
  }
  return (
    strategy.conditions
      ?.map(
        (condition) =>
          `${condition.indicator.toUpperCase()} ${condition.operator} ${condition.value}`
      )
      .join(" AND ") ?? ""
  );
}

export default function StrategiesPage() {
  const router = useRouter();
  const [strategies, setStrategies] = useState<StrategyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [cloningId, setCloningId] = useState<number | null>(null);
  const [deployingId, setDeployingId] = useState<number | null>(null);
  const [deployedIds, setDeployedIds] = useState<Set<number>>(new Set());
  const [deployTarget, setDeployTarget] = useState<StrategyRecord | null>(null);
  const [expandedIssues, setExpandedIssues] = useState<number | null>(null);
  const [overflowOpen, setOverflowOpen] = useState<number | null>(null);
  const { toast } = useToast();

  const fetchStrategies = useCallback(async () => {
    try {
      const data = await apiFetch<{ strategies: StrategyRecord[] }>("/api/strategies/list");
      setStrategies(data.strategies || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  // Close overflow menu when clicking outside
  useEffect(() => {
    if (overflowOpen === null) return;
    const handler = () => setOverflowOpen(null);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [overflowOpen]);

  const deleteStrategy = async (id: number, event: React.MouseEvent) => {
    event.stopPropagation();
    const previous = strategies;
    setStrategies((current) => current.filter((strategy) => strategy.id !== id));
    try {
      await apiFetch(`/api/strategies/${id}`, { method: "DELETE" });
    } catch {
      setStrategies(previous);
    }
  };

  const deployStrategy = (strategy: StrategyRecord, event: React.MouseEvent) => {
    event.stopPropagation();
    setDeployTarget(strategy);
  };

  const handleDeployConfirm = async (config: DeployConfig) => {
    if (!deployTarget) return;
    const strategy = deployTarget;
    setDeployingId(strategy.id);
    try {
      await deployBotFromStrategy(
        strategy.id,
        strategy.name,
        config.universeConfig as unknown as Record<string, unknown>,
        config.overrideLevel,
      );
      setDeployedIds((prev) => new Set(prev).add(strategy.id));
      toast(`"${strategy.name}" deployed as bot`, "success");
      setDeployTarget(null);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to deploy bot";
      toast(msg, "error");
    } finally {
      setDeployingId(null);
    }
  };

  const cloneStrategy = async (strategy: StrategyRecord, event: React.MouseEvent) => {
    event.stopPropagation();
    setCloningId(strategy.id);
    const tempId = -Date.now();
    const optimistic: StrategyRecord = {
      ...strategy,
      id: tempId,
      name: `${strategy.name} (copy)`,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setStrategies((prev) => [optimistic, ...prev]);
    try {
      const created = await apiFetch<StrategyRecord>("/api/strategies/create", {
        method: "POST",
        body: JSON.stringify({
          name: `${strategy.name} (copy)`,
          description: strategy.description,
          condition_groups: strategy.condition_groups,
          conditions: strategy.conditions,
          action: strategy.action,
          stop_loss_pct: strategy.stop_loss_pct,
          take_profit_pct: strategy.take_profit_pct,
          position_size_pct: strategy.position_size_pct,
          timeframe: strategy.timeframe,
          symbols: strategy.symbols,
          commission_pct: strategy.commission_pct,
          slippage_pct: strategy.slippage_pct,
          trailing_stop_pct: strategy.trailing_stop_pct,
          exit_after_bars: strategy.exit_after_bars,
          cooldown_bars: strategy.cooldown_bars,
          max_trades_per_day: strategy.max_trades_per_day,
          max_exposure_pct: strategy.max_exposure_pct,
          max_loss_pct: strategy.max_loss_pct,
          strategy_type: strategy.strategy_type,
          source_prompt: strategy.source_prompt,
          ai_context: strategy.ai_context,
        }),
      });
      setStrategies((prev) =>
        prev.map((item) => (item.id === tempId ? { ...optimistic, id: created.id } : item))
      );
    } catch {
      setStrategies((prev) => prev.filter((item) => item.id !== tempId));
    } finally {
      setCloningId(null);
    }
  };

  return (
    <TooltipProvider>
      <div className="app-page">
        <PageHeader
          eyebrow="Library"
          title="Saved Strategies"
          description="Review strategy diagnostics, duplicate promising setups, launch bots, and jump directly into editing, backtesting, or intelligence workflows."
          meta={
            <Badge variant="neutral" className="tracking-normal">
              <span className="font-mono">{strategies.length}</span>
              strateg{strategies.length !== 1 ? "ies" : "y"}
            </Badge>
          }
          actions={
            <Button asChild variant="primary" size="sm">
              <Link href="/strategy-builder">New Strategy</Link>
            </Button>
          }
        />

        {loading ? (
          <div className="space-y-3">
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </div>
        ) : strategies.length === 0 ? (
          <EmptyState
            icon={<Layers className="h-5 w-5 text-muted-foreground" />}
            title="No strategies yet"
            description="Build your first systematic setup to start backtesting and deploying bots."
            action={
              <Button asChild variant="primary" size="sm">
                <Link href="/strategy-builder">Build your first strategy &rarr;</Link>
              </Button>
            }
          />
        ) : (
          <div className="space-y-3">
            {strategies.map((strategy) => (
              <div
                key={strategy.id}
                onClick={() => router.push(`/edit/${strategy.id}`)}
                className="app-panel group cursor-pointer p-4 card-hover elevation-1 sm:p-5"
              >
                <div className="flex flex-col gap-4 2xl:flex-row 2xl:items-start">
                  <div className="min-w-0 flex-1 space-y-3.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-semibold tracking-tight text-foreground">
                        {strategy.name}
                      </h3>
                      <ScoreBadge score={strategy.diagnostics?.score ?? 0} />
                      <Badge variant="neutral">{strategy.action}</Badge>
                      <Badge variant="neutral">{strategy.timeframe}</Badge>
                      <Badge
                        variant={
                          strategy.strategy_type === "ai_generated"
                            ? "primary"
                            : strategy.strategy_type === "custom"
                              ? "info"
                              : "neutral"
                        }
                      >
                        {strategy.strategy_type === "ai_generated"
                          ? "AI"
                          : strategy.strategy_type === "custom"
                            ? "Custom"
                            : "Manual"}
                      </Badge>
                    </div>

                    <div className="space-y-2">
                      <div className="max-w-4xl">
                        <TokenizedConditions summary={conditionSummary(strategy)} />
                      </div>
                      {strategy.description && (
                        <p className="max-w-3xl text-sm leading-6 text-muted-foreground/80">
                          {strategy.description}
                        </p>
                      )}
                    </div>

                    {expandedIssues === strategy.id && strategy.diagnostics?.diagnostics && (
                      <div className="mt-3 space-y-2 rounded-xl border border-amber-500/15 bg-amber-500/5 p-3">
                        {strategy.diagnostics.diagnostics.map((issue: { message: string; severity: string }) => (
                          <div key={issue.message} className="flex items-start gap-2 text-sm">
                            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
                            <span className="text-muted-foreground">{issue.message}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-muted-foreground">
                      <Badge variant="neutral" className="tracking-normal">
                        <span className="font-mono">{conditionCount(strategy)}</span>
                        conditions
                      </Badge>
                      {strategy.diagnostics?.total_issues > 0 && (
                        <button
                          onClick={(e) => { e.stopPropagation(); setExpandedIssues(prev => prev === strategy.id ? null : strategy.id); }}
                          className="cursor-pointer"
                        >
                          <Badge variant="warning">
                            {strategy.diagnostics.total_issues} issue{strategy.diagnostics.total_issues > 1 ? "s" : ""}
                          </Badge>
                        </button>
                      )}
                      {strategy.updated_at && (
                        <Badge variant="neutral" className="tracking-normal">
                          Updated {relativeTime(strategy.updated_at)}
                        </Badge>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 border-t border-border/50 pt-4 2xl:max-w-[26rem] 2xl:justify-end 2xl:border-t-0 2xl:pt-0">
                    <Button
                      onClick={(e) => { e.stopPropagation(); router.push(`/backtest/${strategy.id}`); }}
                      variant="secondary"
                      size="sm"
                    >
                      <Play className="h-3.5 w-3.5" />
                      Backtest
                    </Button>
                    <Button
                      onClick={(e) => deployStrategy(strategy, e)}
                      disabled={deployingId === strategy.id}
                      variant={deployedIds.has(strategy.id) ? "success" : "primary"}
                      size="sm"
                    >
                      {deployingId === strategy.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Rocket className="h-3.5 w-3.5" />
                      )}
                      {deployedIds.has(strategy.id) ? "Deployed" : "Deploy"}
                    </Button>
                    <div className="relative">
                      <Button
                        onClick={(e) => { e.stopPropagation(); setOverflowOpen(prev => prev === strategy.id ? null : strategy.id); }}
                        variant="subtle"
                        size="icon"
                        className="h-9 w-9"
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                      {overflowOpen === strategy.id && (
                        <div className="absolute right-0 top-full z-20 mt-1 w-40 rounded-xl border border-border/70 bg-card p-1 elevation-2" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={(e) => { e.stopPropagation(); router.push(`/edit/${strategy.id}`); setOverflowOpen(null); }}
                            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                          >
                            <Pencil className="h-3.5 w-3.5" /> Edit
                          </button>
                          <button
                            onClick={(e) => { cloneStrategy(strategy, e); setOverflowOpen(null); }}
                            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                          >
                            <Copy className="h-3.5 w-3.5" /> Clone
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); router.push(`/intelligence/${strategy.id}`); setOverflowOpen(null); }}
                            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                          >
                            <Brain className="h-3.5 w-3.5" /> Intelligence
                          </button>
                          <div className="my-1 border-t border-border/50" />
                          <button
                            onClick={(e) => { if (confirm("Delete this strategy? This action cannot be undone.")) { deleteStrategy(strategy.id, e); } setOverflowOpen(null); }}
                            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-400 hover:bg-red-500/10"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <DeployConfigModal
          open={deployTarget !== null}
          onClose={() => setDeployTarget(null)}
          onDeploy={(config) => void handleDeployConfirm(config)}
          botName={deployTarget?.name}
          isDeploying={deployingId !== null}
        />
      </div>
    </TooltipProvider>
  );
}
