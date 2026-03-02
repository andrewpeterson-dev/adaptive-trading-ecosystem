"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { StrategyBuilder } from "@/components/strategy-builder/StrategyBuilder";
import { apiFetch } from "@/lib/api/client";
import type { StrategyRecord } from "@/types/strategy";
import { Loader2 } from "lucide-react";

export default function EditStrategyPage() {
  const params = useParams();
  const id = params.id as string;
  const [strategy, setStrategy] = useState<StrategyRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch<StrategyRecord>(`/api/strategies/${id}`);
        setStrategy(data);
      } catch {
        setError("Failed to load strategy");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !strategy) {
    return (
      <div className="text-center py-20">
        <p className="text-muted-foreground">{error || "Strategy not found"}</p>
      </div>
    );
  }

  return <StrategyBuilder initialStrategy={strategy} mode="edit" />;
}
