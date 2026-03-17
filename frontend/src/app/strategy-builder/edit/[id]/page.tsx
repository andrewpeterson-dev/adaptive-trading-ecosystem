"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import StrategyBuilderPage from "@/components/strategy-builder/StrategyBuilderPage";
import type { StrategyRecord } from "@/types/strategy";

export default function EditStrategyRoute() {
  const params = useParams<{ id: string }>();
  const [strategy, setStrategy] = useState<StrategyRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.id) return;

    fetch(`/api/strategies/${params.id}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Strategy not found (${res.status})`);
        return res.json();
      })
      .then((data: StrategyRecord) => {
        setStrategy(data);
        setLoading(false);
      })
      .catch((err: Error) => {
        setError(err.message);
        setLoading(false);
      });
  }, [params.id]);

  if (loading) {
    return (
      <div className="app-page p-8 text-center text-muted-foreground">
        Loading strategy...
      </div>
    );
  }

  if (error || !strategy) {
    return (
      <div className="app-page p-8 text-center text-red-400">
        {error ?? "Strategy not found"}
      </div>
    );
  }

  return <StrategyBuilderPage initialStrategy={strategy} />;
}
