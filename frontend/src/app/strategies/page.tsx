"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Trash2, Shield, ChevronRight, Pencil, Play } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
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

export default function StrategiesPage() {
  const router = useRouter();
  const [strategies, setStrategies] = useState<StrategyRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchStrategies = async () => {
    try {
      const data = await apiFetch<any>("/api/strategies/list");
      setStrategies(data.strategies || []);
    } catch {
      // offline
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStrategies();
  }, []);

  const deleteStrategy = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await apiFetch(`/api/strategies/${id}`, { method: "DELETE" });
    setStrategies((prev) => prev.filter((s) => s.id !== id));
  };

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold">Saved Strategies</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {strategies.length} strateg{strategies.length === 1 ? "y" : "ies"} saved
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
        <div className="text-center py-12 text-muted-foreground text-sm">
          Loading strategies...
        </div>
      ) : strategies.length === 0 ? (
        <div className="text-center py-12 border border-dashed rounded-lg">
          <Shield className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-muted-foreground">No strategies yet</p>
          <Link
            href="/"
            className="text-primary text-sm mt-1 inline-block hover:underline"
          >
            Create your first strategy
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {strategies.map((s) => (
            <div
              key={s.id}
              onClick={() => router.push(`/edit/${s.id}`)}
              className="flex items-center gap-4 p-4 rounded-lg border border-border/50 bg-card hover:border-primary/30 hover:bg-card/80 transition-colors group cursor-pointer"
            >
              <ScoreBadge score={s.diagnostics?.score ?? 0} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium truncate">{s.name}</h3>
                  <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                    {s.action}
                  </span>
                  <span className="text-xs text-muted-foreground font-mono">
                    #{s.id}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5 truncate">
                  {s.conditions
                    ?.map(
                      (c) =>
                        `${c.indicator.toUpperCase()} ${c.operator} ${c.value}`
                    )
                    .join(" AND ")}
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                {s.diagnostics?.total_issues > 0 && (
                  <span className="text-xs text-muted-foreground">
                    {s.diagnostics.total_issues} issue
                    {s.diagnostics.total_issues > 1 ? "s" : ""}
                  </span>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    router.push(`/backtest/${s.id}`);
                  }}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-amber-400 hover:bg-amber-400/10 transition-colors"
                  title="Backtest"
                >
                  <Play className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    router.push(`/edit/${s.id}`);
                  }}
                  className="p-1.5 rounded text-muted-foreground/40 hover:text-primary hover:bg-primary/10 transition-colors"
                  title="Edit"
                >
                  <Pencil className="h-4 w-4" />
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
