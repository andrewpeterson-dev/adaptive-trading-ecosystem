"use client";

import React, { useEffect, useState } from "react";
import { Trophy, ArrowUpRight } from "lucide-react";
import { getModelComparison, updateBotModel, type ModelComparisonData } from "@/lib/cerberus-api";

interface ModelLeaderboardProps {
  botId: string;
  onUpdate?: () => void;
}

export function ModelLeaderboard({ botId, onUpdate }: ModelLeaderboardProps) {
  const [data, setData] = useState<ModelComparisonData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    getModelComparison(botId)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, [botId]);

  const handlePromote = async (model: string) => {
    if (!confirm(`Switch primary model to ${model}?`)) return;
    await updateBotModel(botId, model);
    load();
    onUpdate?.();
  };

  if (loading) return <div className="text-sm text-zinc-500 p-4">Loading model data...</div>;
  if (!data || data.models.length === 0) return <div className="text-sm text-zinc-500 p-4">No model comparison data yet.</div>;

  const bestIdx = 0; // Already sorted by score from the API

  return (
    <div className="rounded-lg border border-border bg-muted/15 overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        <Trophy className="w-4 h-4 text-yellow-400" />
        <h3 className="text-sm font-medium text-zinc-200">Model Leaderboard</h3>
        {data.auto_route_enabled && (
          <span className="ml-auto text-[10px] text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-full">
            Auto-routing active
          </span>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-700 text-xs text-zinc-400">
              <th className="px-3 py-2 text-left">Model</th>
              <th className="px-3 py-2 text-right">Trades</th>
              <th className="px-3 py-2 text-right">Win Rate</th>
              <th className="px-3 py-2 text-right">Avg Return</th>
              <th className="px-3 py-2 text-right">Sharpe</th>
              <th className="px-3 py-2 text-right">Drawdown</th>
              <th className="px-3 py-2 text-right">Total P&L</th>
              <th className="px-3 py-2 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-700/50">
            {data.models.map((m, i) => (
              <tr key={m.model} className={`hover:bg-zinc-700/20 ${i === bestIdx ? "bg-emerald-400/5" : ""}`}>
                <td className="px-3 py-2 text-zinc-200 font-mono text-xs">
                  {m.model}
                  {m.is_primary && (
                    <span className="ml-2 text-[9px] text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded">
                      primary
                    </span>
                  )}
                  {i === bestIdx && (
                    <span className="ml-1 text-[9px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                      best
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-right text-zinc-300 tabular-nums">{m.trades_count}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className={m.win_rate >= 0.5 ? "text-green-400" : "text-red-400"}>
                    {(m.win_rate * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className={m.avg_return >= 0 ? "text-green-400" : "text-red-400"}>
                    ${m.avg_return.toFixed(2)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className={m.sharpe_ratio >= 1 ? "text-green-400" : m.sharpe_ratio >= 0 ? "text-zinc-300" : "text-red-400"}>
                    {m.sharpe_ratio.toFixed(2)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className="text-red-400">{m.max_drawdown.toFixed(2)}</span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  <span className={m.total_pnl >= 0 ? "text-green-400" : "text-red-400"}>
                    ${m.total_pnl.toFixed(2)}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  {!m.is_primary && (
                    <button
                      onClick={() => handlePromote(m.model)}
                      className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                    >
                      <ArrowUpRight className="w-3 h-3" /> Use
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
