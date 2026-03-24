"use client";

import { useEffect, useState } from "react";
import { GraduationCap, BarChart3, BookOpen } from "lucide-react";
import {
  getBotJournal,
  getBotRegimeStats,
  getBotAdaptations,
  type JournalEntry,
  type RegimeStat,
  type Adaptation,
} from "@/lib/reasoning-api";

function RegimeChart({ stats }: { stats: RegimeStat[] }) {
  if (stats.length === 0) {
    return (
      <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-6 text-center text-sm text-muted-foreground">
        No regime data yet
      </div>
    );
  }

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {stats.map((s) => {
        const winColor = s.win_rate >= 0.6 ? "text-emerald-400" : s.win_rate >= 0.4 ? "text-amber-400" : "text-rose-400";
        return (
          <div key={s.regime} className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3">
            <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              {s.regime.replace(/_/g, " ")}
            </div>
            <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
              <div>
                <div className="text-[9px] uppercase text-muted-foreground/60">Win Rate</div>
                <div className={`text-sm font-bold tabular-nums ${winColor}`}>
                  {(s.win_rate * 100).toFixed(0)}%
                </div>
              </div>
              <div>
                <div className="text-[9px] uppercase text-muted-foreground/60">Trades</div>
                <div className="text-sm font-semibold tabular-nums text-foreground">{s.total_trades}</div>
              </div>
              <div>
                <div className="text-[9px] uppercase text-muted-foreground/60">Avg PnL</div>
                <div className={`text-sm font-semibold tabular-nums ${s.avg_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {s.avg_pnl >= 0 ? "+" : ""}{s.avg_pnl.toFixed(2)}%
                </div>
              </div>
              <div>
                <div className="text-[9px] uppercase text-muted-foreground/60">Sharpe</div>
                <div className="text-sm font-semibold tabular-nums text-foreground">{s.sharpe.toFixed(2)}</div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function LearningTab({ botId }: { botId: string }) {
  const [journal, setJournal] = useState<JournalEntry[]>([]);
  const [regimeStats, setRegimeStats] = useState<RegimeStat[]>([]);
  const [adaptations, setAdaptations] = useState<Adaptation[]>([]);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    setLoadError(false);
    Promise.all([
      getBotJournal(botId).then(setJournal),
      getBotRegimeStats(botId).then(setRegimeStats),
      getBotAdaptations(botId).then(setAdaptations),
    ]).catch(() => setLoadError(true));
  }, [botId]);

  return (
    <div className="space-y-6">
      {loadError && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 px-4 py-3 text-xs text-amber-400">
          Some learning data failed to load. Showing what&apos;s available.
        </div>
      )}
      {/* Regime Stats */}
      <div className="app-panel p-5 sm:p-6">
        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          <BarChart3 className="h-3.5 w-3.5 text-sky-400" />
          Regime Performance
        </div>
        <div className="mt-4">
          <RegimeChart stats={regimeStats} />
        </div>
      </div>

      {/* Adaptations */}
      <div className="app-panel p-5 sm:p-6">
        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          <GraduationCap className="h-3.5 w-3.5 text-violet-400" />
          Adaptations Log
        </div>
        <div className="mt-4 max-h-[300px] space-y-2 overflow-y-auto">
          {adaptations.length === 0 ? (
            <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-6 text-center text-sm text-muted-foreground">
              No adaptations yet
            </div>
          ) : (
            adaptations.map((a) => (
              <div key={a.id} className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="app-pill px-2 py-0.5 text-[10px] font-mono">{a.adaptation_type}</span>
                    {a.auto_applied && (
                      <span className="rounded-full border border-emerald-400/20 bg-emerald-400/8 px-2 py-0.5 text-[9px] font-bold uppercase text-emerald-400">
                        Auto-applied
                      </span>
                    )}
                  </div>
                  <span className="text-[10px] text-muted-foreground">
                    {a.created_at ? new Date(a.created_at).toLocaleDateString() : ""}
                  </span>
                </div>
                <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{a.reasoning}</p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Trade Journal */}
      <div className="app-panel p-5 sm:p-6">
        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          <BookOpen className="h-3.5 w-3.5 text-amber-400" />
          Trade Journal
        </div>
        <div className="mt-4 max-h-[400px] space-y-2 overflow-y-auto">
          {journal.length === 0 ? (
            <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-6 text-center text-sm text-muted-foreground">
              No journal entries yet
            </div>
          ) : (
            journal.map((j) => (
              <div key={j.id} className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-foreground">{j.symbol}</span>
                    <span className={`text-xs font-semibold uppercase ${j.side === "BUY" ? "text-emerald-400" : "text-rose-400"}`}>
                      {j.side}
                    </span>
                    {j.pnl_pct != null && (
                      <span className={`text-xs font-semibold tabular-nums ${j.pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                        {j.pnl_pct >= 0 ? "+" : ""}{j.pnl_pct.toFixed(1)}%
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {j.regime_at_entry && (
                      <span className="app-pill px-2 py-0.5 text-[9px] font-mono">{j.regime_at_entry}</span>
                    )}
                    <span className="text-[10px] text-muted-foreground">
                      {j.created_at ? new Date(j.created_at).toLocaleDateString() : ""}
                    </span>
                  </div>
                </div>
                {j.ai_reasoning && (
                  <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{j.ai_reasoning}</p>
                )}
                {j.lesson_learned && (
                  <p className="mt-1 text-xs italic text-muted-foreground/70">{j.lesson_learned}</p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
