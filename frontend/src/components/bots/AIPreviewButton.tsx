"use client";

import React, { useState } from "react";
import { Eye, Loader2 } from "lucide-react";
import { AIReasoningPanel } from "./AIReasoningPanel";

interface AIPreviewButtonProps {
  botId: string;
  token: string;
}

export function AIPreviewButton({ botId, token }: AIPreviewButtonProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handlePreview = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`/api/bots/${botId}/ai-preview`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Preview failed");
      }
      const data = await res.json();
      setResult(data.decision);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <button
        onClick={handlePreview}
        disabled={loading}
        className="flex items-center gap-2 px-3 py-1.5 text-sm rounded border border-zinc-600 text-zinc-300 hover:text-white hover:border-zinc-500 transition-colors disabled:opacity-50"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
        {loading ? "Running AI..." : "What would AI do?"}
      </button>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {result && (
        <AIReasoningPanel
          action={result.action}
          symbol={result.symbol}
          confidence={result.confidence}
          reasoningSummary={result.reasoning_summary}
          dataContributions={result.data_contributions}
          nodes={result.reasoning_full ? Object.entries(result.reasoning_full).map(([name, output]) => ({ name, output })) : undefined}
          modelUsed={result.model_used}
        />
      )}
    </div>
  );
}
