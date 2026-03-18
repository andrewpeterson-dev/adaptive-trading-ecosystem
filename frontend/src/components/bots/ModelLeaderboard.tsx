"use client";

import React, { useEffect, useState } from "react";
import { Trophy, ArrowUpRight } from "lucide-react";

interface ModelMetrics {
  model: string;
  is_primary: boolean;
  total_decisions: number;
  win_rate: number | null;
  avg_confidence: number;
  total_pnl: number;
}

interface ModelLeaderboardProps {
  botId: string;
  token: string;
}

export function ModelLeaderboard({ botId, token }: ModelLeaderboardProps) {
  const [models, setModels] = useState<ModelMetrics[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/bots/${botId}/model-comparison`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setModels(data.models || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [botId, token]);

  if (loading) return <div className="text-sm text-zinc-500 p-4">Loading model data...</div>;
  if (models.length === 0) return <div className="text-sm text-zinc-500 p-4">No model comparison data yet.</div>;

  const handlePromote = async (model: string) => {
    if (!confirm(`Switch primary model to ${model}? Takes effect next evaluation cycle.`)) return;
    await fetch(`/api/bots/${botId}/ai-config`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model_config: { primary_model: model } }),
    });
    window.location.reload();
  };

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-700 flex items-center gap-2">
        <Trophy className="w-4 h-4 text-yellow-400" />
        <h3 className="text-sm font-medium text-zinc-200">Model Comparison</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-700 text-xs text-zinc-400">
              <th className="px-4 py-2 text-left">Model</th>
              <th className="px-4 py-2 text-right">Decisions</th>
              <th className="px-4 py-2 text-right">Win Rate</th>
              <th className="px-4 py-2 text-right">Avg Conf</th>
              <th className="px-4 py-2 text-right">Total P&L</th>
              <th className="px-4 py-2 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-700/50">
            {models.map((m) => (
              <tr key={m.model} className="hover:bg-zinc-700/20">
                <td className="px-4 py-2 text-zinc-200">
                  {m.model}
                  {m.is_primary && (
                    <span className="ml-2 text-xs text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded">
                      primary
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-right text-zinc-300">{m.total_decisions}</td>
                <td className="px-4 py-2 text-right">
                  {m.win_rate !== null ? (
                    <span className={m.win_rate >= 0.5 ? "text-green-400" : "text-red-400"}>
                      {(m.win_rate * 100).toFixed(0)}%
                    </span>
                  ) : (
                    <span className="text-zinc-500">--</span>
                  )}
                </td>
                <td className="px-4 py-2 text-right text-zinc-300">
                  {(m.avg_confidence * 100).toFixed(0)}%
                </td>
                <td className="px-4 py-2 text-right">
                  <span className={m.total_pnl >= 0 ? "text-green-400" : "text-red-400"}>
                    ${m.total_pnl.toFixed(2)}
                  </span>
                </td>
                <td className="px-4 py-2 text-right">
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
