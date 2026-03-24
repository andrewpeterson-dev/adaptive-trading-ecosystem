"use client";

import { useEffect, useState } from "react";
import { Brain } from "lucide-react";
import { getBotDecisions, type TradeDecisionItem } from "@/lib/reasoning-api";

const DECISION_COLORS: Record<string, string> = {
  EXECUTE: "text-emerald-400 border-emerald-400/20 bg-emerald-400/8",
  REDUCE_SIZE: "text-amber-400 border-amber-400/20 bg-amber-400/8",
  DELAY_TRADE: "text-amber-400 border-amber-400/20 bg-amber-400/8",
  PAUSE_BOT: "text-rose-400 border-rose-400/20 bg-rose-400/8",
  EXIT_POSITION: "text-rose-400 border-rose-400/20 bg-rose-400/8",
};

const RISK_COLORS: Record<string, string> = {
  LOW: "text-emerald-400",
  MEDIUM: "text-amber-400",
  HIGH: "text-rose-400",
  CRITICAL: "text-rose-500",
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "bg-emerald-400" : pct >= 40 ? "bg-amber-400" : "bg-rose-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-muted/30">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold tabular-nums text-foreground">{pct}%</span>
    </div>
  );
}

export function AIReasoningTab({ botId }: { botId: string }) {
  const [decisions, setDecisions] = useState<TradeDecisionItem[]>([]);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    setLoadError(false);
    getBotDecisions(botId).then(setDecisions).catch(() => setLoadError(true));
  }, [botId]);

  const latest = decisions[0];

  return (
    <div className="space-y-6">
      {loadError && decisions.length === 0 && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/5 px-4 py-3 text-xs text-amber-400">
          Failed to load AI reasoning data.
        </div>
      )}
      {latest && (
        <div className="app-panel p-5 sm:p-6">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            <Brain className="h-3.5 w-3.5 text-violet-400" />
            Latest Decision
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Decision</div>
              <div className={`mt-1 inline-flex rounded-full border px-3 py-1 text-xs font-bold uppercase ${DECISION_COLORS[latest.decision] ?? ""}`}>
                {latest.decision}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Confidence</div>
              <div className="mt-1"><ConfidenceBar value={latest.ai_confidence} /></div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Risk Level</div>
              <div className={`mt-1 text-sm font-semibold ${RISK_COLORS[latest.context_risk_level] ?? ""}`}>
                {latest.context_risk_level}
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Model</div>
              <div className="mt-1 text-sm font-mono text-foreground">{latest.model_used}</div>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-border/60 bg-muted/10 p-4">
            <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Reasoning</div>
            <p className="mt-1.5 text-sm leading-6 text-foreground">{latest.reasoning}</p>
          </div>
        </div>
      )}

      <div className="app-panel p-5 sm:p-6">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Decision Timeline
        </div>
        <div className="mt-4 max-h-[400px] space-y-2 overflow-y-auto">
          {decisions.length === 0 ? (
            <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-6 text-center text-sm text-muted-foreground">
              No decisions recorded yet
            </div>
          ) : (
            decisions.map((d) => (
              <div key={d.id} className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${DECISION_COLORS[d.decision] ?? ""}`}>
                      {d.decision}
                    </span>
                    <span className="font-mono text-sm text-foreground">{d.symbol}</span>
                    <span className="text-xs text-muted-foreground">{d.strategy_signal}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <ConfidenceBar value={d.ai_confidence} />
                    <span className="text-[10px] text-muted-foreground">
                      {d.created_at ? new Date(d.created_at).toLocaleString() : ""}
                    </span>
                  </div>
                </div>
                {d.reasoning && (
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{d.reasoning}</p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
