"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, Brain, Zap } from "lucide-react";

interface NodeReasoning {
  name: string;
  output: any;
  model?: string;
  tokens?: number;
  latency_ms?: number;
}

interface AIReasoningPanelProps {
  action: "BUY" | "SELL" | "HOLD" | "EXIT" | string;
  symbol: string;
  confidence: number;
  reasoningSummary: string;
  dataContributions?: Record<string, number>;
  nodes?: NodeReasoning[];
  modelUsed?: string;
}

export function AIReasoningPanel({
  action,
  symbol,
  confidence,
  reasoningSummary,
  dataContributions,
  nodes,
  modelUsed,
}: AIReasoningPanelProps) {
  const [expanded, setExpanded] = useState(false);

  const confidenceColor =
    confidence >= 0.7 ? "text-green-400" : confidence >= 0.4 ? "text-yellow-400" : "text-red-400";
  const confidenceBg =
    confidence >= 0.7 ? "bg-green-500/10 border-green-500/30" : confidence >= 0.4 ? "bg-yellow-500/10 border-yellow-500/30" : "bg-red-500/10 border-red-500/30";

  const actionColor: Record<string, string> = {
    BUY: "text-green-400 bg-green-500/10",
    SELL: "text-red-400 bg-red-500/10",
    HOLD: "text-zinc-400 bg-zinc-500/10",
    EXIT: "text-orange-400 bg-orange-500/10",
  };

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 overflow-hidden">
      {/* Tier B — Summary */}
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-blue-400" />
            <span className={`text-xs font-medium px-2 py-0.5 rounded ${actionColor[action] || ""}`}>
              {action} {symbol}
            </span>
          </div>
          <div className={`text-sm font-mono px-2 py-0.5 rounded border ${confidenceBg}`}>
            <span className={confidenceColor}>{(confidence * 100).toFixed(0)}%</span>
          </div>
        </div>

        <p className="text-sm text-zinc-300">{reasoningSummary}</p>

        {dataContributions && Object.keys(dataContributions).length > 0 && (
          <div className="space-y-1">
            <span className="text-xs text-zinc-500">Data Contributions</span>
            <div className="flex gap-1">
              {Object.entries(dataContributions).map(([source, weight]) => (
                <div key={source} className="flex-1">
                  <div className="text-xs text-zinc-400 mb-0.5 capitalize">{source}</div>
                  <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full"
                      style={{ width: `${weight * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {modelUsed && (
          <div className="flex items-center gap-1 text-xs text-zinc-500">
            <Zap className="w-3 h-3" />
            {modelUsed}
          </div>
        )}
      </div>

      {/* Tier C — Expandable */}
      {nodes && nodes.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full px-4 py-2 flex items-center justify-between text-xs text-zinc-400 hover:text-zinc-300 border-t border-zinc-700 transition-colors"
          >
            <span>Full Analysis ({nodes.length} nodes)</span>
            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>

          {expanded && (
            <div className="border-t border-zinc-700 divide-y divide-zinc-700/50">
              {nodes.map((node, i) => (
                <div key={`${node.name}-${i}`} className="p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-zinc-300 capitalize">
                      {node.name.replace(/_/g, " ")}
                    </span>
                    <div className="flex gap-2 text-xs text-zinc-500">
                      {node.model && <span>{node.model}</span>}
                      {node.tokens && <span>{node.tokens} tok</span>}
                      {node.latency_ms && <span>{node.latency_ms}ms</span>}
                    </div>
                  </div>
                  <p className="text-xs text-zinc-400 whitespace-pre-wrap">
                    {typeof node.output === "string"
                      ? node.output
                      : JSON.stringify(node.output?.report || node.output, null, 2)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
