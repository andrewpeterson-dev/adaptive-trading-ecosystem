"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Trash2,
  Shield,
  ChevronRight,
  Pencil,
  Play,
  Copy,
  Rocket,
  Brain,
  Loader2,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { deployBotFromStrategy } from "@/lib/cerberus-api";
import type { StrategyRecord } from "@/types/strategy";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";

function ScoreBadge({ score }: { score: number }) {
  if (score >= 80) return <Badge variant="success">Score {score}</Badge>;
  if (score >= 50) return <Badge variant="warning">Score {score}</Badge>;
  return <Badge variant="danger">Score {score}</Badge>;
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

  const deployStrategy = async (strategy: StrategyRecord, event: React.MouseEvent) => {
    event.stopPropagation();
    setDeployingId(strategy.id);
    try {
      await deployBotFromStrategy(strategy.id, strategy.name);
      setDeployedIds((prev) => new Set(prev).add(strategy.id));
      toast(`"${strategy.name}" deployed as bot`, "success");
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
    <div className="app-page">
      <PageHeader
        eyebrow="Library"
        title="Saved Strategies"
        description="Review strategy diagnostics, duplicate promising setups, launch bots, and jump directly into editing, backtesting, or intelligence workflows."
        meta={
          <Badge variant="neutral" className="tracking-normal">
            <span className="font-mono">{strategies.length}</span>
            strategy{strategies.length !== 1 ? "ies" : ""}
          </Badge>
        }
        actions={
          <Button asChild variant="primary" size="sm">
            <Link href="/">New Strategy</Link>
          </Button>
        }
      />

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : strategies.length === 0 ? (
        <EmptyState
          icon={<Shield className="h-5 w-5 text-muted-foreground" />}
          title="No strategies saved"
          description="Build your first systematic setup to start backtesting, deploying bots, and reviewing AI intelligence."
          action={
            <Button asChild variant="primary" size="sm">
              <Link href="/">Create Strategy</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {strategies.map((strategy) => (
            <div
              key={strategy.id}
              onClick={() => router.push(`/edit/${strategy.id}`)}
              className="app-panel cursor-pointer p-4 transition-transform hover:-translate-y-0.5 sm:p-5"
            >
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start">
                <div className="flex flex-1 flex-col gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <ScoreBadge score={strategy.diagnostics?.score ?? 0} />
                    <h3 className="text-lg font-semibold tracking-tight text-foreground">
                      {strategy.name}
                    </h3>
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

                  <p className="max-w-4xl text-sm leading-6 text-muted-foreground">
                    {conditionSummary(strategy) || "No conditions defined yet."}
                  </p>

                  {strategy.description && (
                    <p className="text-sm italic text-muted-foreground/80">
                      {strategy.description}
                    </p>
                  )}

                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <Badge variant="neutral" className="tracking-normal">
                      <span className="font-mono">{conditionCount(strategy)}</span>
                      conditions
                    </Badge>
                    {strategy.diagnostics?.total_issues > 0 && (
                      <Badge variant="warning">
                        {strategy.diagnostics.total_issues} issue
                        {strategy.diagnostics.total_issues > 1 ? "s" : ""}
                      </Badge>
                    )}
                    {strategy.updated_at && (
                      <Badge variant="neutral" className="tracking-normal">
                        Updated {relativeTime(strategy.updated_at)}
                      </Badge>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 xl:justify-end">
                  <Button
                    onClick={(event) => {
                      event.stopPropagation();
                      router.push(`/backtest/${strategy.id}`);
                    }}
                    variant="secondary"
                    size="sm"
                  >
                    <Play className="h-3.5 w-3.5" />
                    Backtest
                  </Button>
                  <Button
                    onClick={(event) => deployStrategy(strategy, event)}
                    disabled={deployingId === strategy.id}
                    variant={deployedIds.has(strategy.id) ? "success" : "secondary"}
                    size="sm"
                  >
                    {deployingId === strategy.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Rocket className="h-3.5 w-3.5" />
                    )}
                    {deployedIds.has(strategy.id) ? "Deployed" : "Deploy"}
                  </Button>
                  <Button
                    onClick={(event) => {
                      event.stopPropagation();
                      router.push(`/edit/${strategy.id}`);
                    }}
                    variant="secondary"
                    size="sm"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                    Edit
                  </Button>
                  <Button
                    onClick={(event) => cloneStrategy(strategy, event)}
                    disabled={cloningId === strategy.id}
                    variant="secondary"
                    size="sm"
                  >
                    {cloningId === strategy.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                    Clone
                  </Button>
                  <Button
                    onClick={(event) => {
                      event.stopPropagation();
                      router.push(`/intelligence/${strategy.id}`);
                    }}
                    variant="secondary"
                    size="sm"
                  >
                    <Brain className="h-3.5 w-3.5" />
                    Intelligence
                  </Button>
                  <Button
                    onClick={(event) => deleteStrategy(strategy.id, event)}
                    variant="danger"
                    size="sm"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </Button>
                  <ChevronRight className="hidden h-4 w-4 text-muted-foreground/50 xl:block" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
