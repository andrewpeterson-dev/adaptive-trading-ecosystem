"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Trash2, Shield, ChevronRight, Pencil, Play, Copy, Rocket, Brain } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { deployBotFromStrategy } from "@/lib/cerberus-api";
import type { StrategyRecord } from "@/types/strategy";

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
      : score >= 50
        ? "text-amber-400 bg-amber-400/10 border-amber-400/20"
        : "text-red-400 bg-red-400/10 border-red-400/20";
  return (
    <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${color}`}>
      {score}
    </span>
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

function conditionCount(s: StrategyRecord): number {
  if (s.condition_groups?.length) {
    return s.condition_groups.reduce((sum, g) => sum + (g.conditions?.length ?? 0), 0);
  }
  return s.conditions?.length ?? 0;
}

function conditionSummary(s: StrategyRecord): string {
  if (s.condition_groups?.length) {
    return s.condition_groups
      .map((g) =>
        g.conditions
          .map((c) => `${c.indicator.toUpperCase()} ${c.operator} ${c.value}`)
          .join(" AND ")
      )
      .join(" OR ");
  }
  return s.conditions
    ?.map((c) => `${c.indicator.toUpperCase()} ${c.operator} ${c.value}`)
    .join(" AND ") ?? "";
}

export default function StrategiesPage() {
  const router = useRouter();
  const [strategies, setStrategies] = useState<StrategyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [cloningId, setCloningId] = useState<number | null>(null);
  const [deployingId, setDeployingId] = useState<number | null>(null);
  const [deployedIds, setDeployedIds] = useState<Set<number>>(new Set());

  const fetchStrategies = useCallback(async () => {
    try {
      const data = await apiFetch<{ strategies: StrategyRecord[] }>("/api/strategies/list");
      setStrategies(data.strategies || []);
    } catch {
      // offline
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchStrategies(); }, [fetchStrategies]);

  const deleteStrategy = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    // Optimistic remove
    const prev = strategies;
    setStrategies((s) => s.filter((x) => x.id !== id));
    try {
      await apiFetch(`/api/strategies/${id}`, { method: "DELETE" });
    } catch {
      // Revert if API fails
      setStrategies(prev);
    }
  };

  const deployStrategy = async (s: StrategyRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeployingId(s.id);
    try {
      await deployBotFromStrategy(s.id, s.name);
      setDeployedIds((prev) => new Set(prev).add(s.id));
    } catch {
      // show nothing — user can retry
    } finally {
      setDeployingId(null);
    }
  };

  const cloneStrategy = async (s: StrategyRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    setCloningId(s.id);
    // Optimistic insert
    const tempId = -Date.now();
    const optimistic: StrategyRecord = {
      ...s,
      id: tempId,
      name: `${s.name} (copy)`,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setStrategies((prev) => [optimistic, ...prev]);
    try {
      const created = await apiFetch<StrategyRecord>("/api/strategies/create", {
        method: "POST",
        body: JSON.stringify({
          name: `${s.name} (copy)`,
          description: s.description,
          condition_groups: s.condition_groups,
          conditions: s.conditions,
          action: s.action,
          stop_loss_pct: s.stop_loss_pct,
          take_profit_pct: s.take_profit_pct,
          position_size_pct: s.position_size_pct,
          timeframe: s.timeframe,
          symbols: s.symbols,
          commission_pct: s.commission_pct,
          slippage_pct: s.slippage_pct,
          trailing_stop_pct: s.trailing_stop_pct,
          exit_after_bars: s.exit_after_bars,
          cooldown_bars: s.cooldown_bars,
          max_trades_per_day: s.max_trades_per_day,
          max_exposure_pct: s.max_exposure_pct,
          max_loss_pct: s.max_loss_pct,
          strategy_type: s.strategy_type,
          source_prompt: s.source_prompt,
          ai_context: s.ai_context,
        }),
      });
      // Replace optimistic with real
      setStrategies((prev) =>
        prev.map((x) => (x.id === tempId ? { ...optimistic, id: created.id } : x))
      );
    } catch {
      // Revert
      setStrategies((prev) => prev.filter((x) => x.id !== tempId));
    } finally {
      setCloningId(null);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold">Saved Strategies</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {strategies.length} {strategies.length === 1 ? "strategy" : "strategies"} saved
          </p>
        </div>
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors"
        >
          New Strategy
        </Link>
      </div>

      {loading ? (
        <div className="text-center py-12 text-muted-foreground text-sm">Loading strategies...</div>
      ) : strategies.length === 0 ? (
        <div className="text-center py-12 border border-dashed rounded-lg">
          <Shield className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-muted-foreground">No strategies yet</p>
          <Link href="/" className="text-primary text-sm mt-1 inline-block hover:underline">
            Create your first strategy
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {strategies.map((s) => (
            <div
              key={s.id}
              onClick={() => router.push(`/edit/${s.id}`)}
              className="flex items-start gap-4 p-4 rounded-lg border border-border/50 bg-card hover:border-primary/30 hover:bg-card/80 transition-colors group cursor-pointer"
            >
              <ScoreBadge score={s.diagnostics?.score ?? 0} />

              <div className="flex-1 min-w-0">
                {/* Row 1: Name + badges */}
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-medium truncate">{s.name}</h3>
                  <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                    {s.action}
                  </span>
                  <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                    {s.timeframe}
                  </span>
                  <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400">
                    {s.strategy_type === "ai_generated"
                      ? "AI"
                      : s.strategy_type === "custom"
                        ? "Custom"
                        : "Manual"}
                  </span>
                  {s.id > 0 && (
                    <span className="text-xs text-muted-foreground/50 font-mono">#{s.id}</span>
                  )}
                </div>
                {/* Row 2: Condition summary */}
                <p className="text-xs text-muted-foreground mt-0.5 truncate">
                  {conditionSummary(s) || "No conditions defined"}
                </p>
                {/* Row 3: Description */}
                {s.description && (
                  <p className="text-xs text-muted-foreground/70 mt-0.5 truncate italic">
                    {s.description}
                  </p>
                )}
                {/* Row 4: Metadata */}
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[10px] text-muted-foreground/60">
                    {conditionCount(s)} condition{conditionCount(s) !== 1 ? "s" : ""}
                  </span>
                  {s.diagnostics?.total_issues > 0 && (
                    <span className="text-[10px] text-amber-400/80">
                      {s.diagnostics.total_issues} issue{s.diagnostics.total_issues > 1 ? "s" : ""}
                    </span>
                  )}
                  {s.updated_at && (
                    <span className="text-[10px] text-muted-foreground/50">
                      {relativeTime(s.updated_at)}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={(e) => { e.stopPropagation(); router.push(`/backtest/${s.id}`); }}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-amber-400 hover:bg-amber-400/10 transition-colors"
                  title="Backtest"
                >
                  <Play className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => deployStrategy(s, e)}
                  disabled={deployingId === s.id}
                  title={deployedIds.has(s.id) ? "Bot deployed" : "Deploy as live bot"}
                  className={`p-1.5 rounded transition-colors disabled:opacity-40 ${
                    deployedIds.has(s.id)
                      ? "text-emerald-400 bg-emerald-400/10"
                      : "text-muted-foreground/40 hover:text-emerald-400 hover:bg-emerald-400/10"
                  }`}
                >
                  <Rocket className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); router.push(`/edit/${s.id}`); }}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-primary hover:bg-primary/10 transition-colors"
                  title="Edit"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => cloneStrategy(s, e)}
                  disabled={cloningId === s.id}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-sky-400 hover:bg-sky-400/10 transition-colors disabled:opacity-30"
                  title="Clone"
                >
                  <Copy className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); router.push(`/intelligence/${s.id}`); }}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-purple-400 hover:bg-purple-400/10 transition-colors"
                  title="Intelligence"
                >
                  <Brain className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => deleteStrategy(s.id, e)}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
                <ChevronRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-primary transition-colors" />
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
