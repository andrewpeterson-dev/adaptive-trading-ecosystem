"use client";

import { useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { getRecentDecisions, type AIDecisionItem } from "@/lib/cerberus-api";

const ACTION_COLORS: Record<string, string> = {
  BUY: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  SELL: "text-rose-400 bg-rose-400/10 border-rose-400/20",
  EXIT: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  HOLD: "text-zinc-400 bg-zinc-400/10 border-zinc-400/20",
};

export function LiveDecisionFeed({ botId }: { botId: string }) {
  const [decisions, setDecisions] = useState<AIDecisionItem[]>([]);

  useEffect(() => {
    const load = () => {
      getRecentDecisions(botId, 15).then((r) => setDecisions(r.decisions)).catch(() => {});
    };
    load();
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, [botId]);

  return (
    <div className="app-panel overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <Activity className="w-4 h-4 text-sky-400" />
        <h3 className="text-sm font-medium text-zinc-200">AI Decision Feed</h3>
        <span className="ml-auto text-[10px] text-muted-foreground">{decisions.length} recent</span>
      </div>
      <div className="max-h-[400px] overflow-y-auto divide-y divide-border/30">
        {decisions.length === 0 ? (
          <div className="px-4 py-6 text-center text-sm text-muted-foreground">
            No AI decisions recorded yet
          </div>
        ) : (
          decisions.map((d) => (
            <div key={d.id} className="px-4 py-3 hover:bg-muted/10">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${ACTION_COLORS[d.action] ?? ""}`}>
                    {d.action}
                  </span>
                  <span className="font-mono text-sm text-foreground">{d.symbol}</span>
                  <span className="text-[10px] font-mono text-muted-foreground">{d.model_used}</span>
                  {d.is_shadow && (
                    <span className="text-[9px] text-zinc-500 bg-zinc-500/10 px-1 py-0.5 rounded">shadow</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs tabular-nums text-foreground">
                    {d.confidence ? `${(d.confidence * 100).toFixed(0)}%` : "--"}
                  </span>
                  {d.pnl !== null && (
                    <span className={`text-xs tabular-nums ${d.pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                      {d.pnl >= 0 ? "+" : ""}{d.pnl.toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
              {d.reasoning_summary && (
                <p className="mt-1 text-[11px] text-muted-foreground leading-4 line-clamp-2">
                  {d.reasoning_summary}
                </p>
              )}
              <div className="mt-1 text-[10px] text-muted-foreground/60">
                {d.decided_at ? new Date(d.decided_at).toLocaleString() : ""}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
