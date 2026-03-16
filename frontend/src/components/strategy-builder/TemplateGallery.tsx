"use client";

import { useEffect, useMemo, useState } from "react";
import { useBuilderStore } from "@/stores/builder-store";
import { parseStrategySpec } from "@/lib/strategy-spec";
import { apiFetch } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TemplateGalleryProps {
  onModeSwitch: (mode: "ai" | "manual" | "template") => void;
}

// ---------------------------------------------------------------------------
// Type badge color map
// ---------------------------------------------------------------------------

const TYPE_COLORS: Record<string, string> = {
  momentum: "bg-emerald-500/20 text-emerald-400",
  mean_reversion: "bg-purple-500/20 text-purple-400",
  breakout: "bg-blue-500/20 text-blue-400",
  trend: "bg-amber-500/20 text-amber-400",
};

function typeBadgeClass(type: string): string {
  return TYPE_COLORS[type] ?? "bg-zinc-500/20 text-zinc-400";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TemplateGallery({ onModeSwitch }: TemplateGalleryProps) {
  const [templates, setTemplates] = useState<any[]>([]);
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  // ---- Fetch templates on mount ----
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setIsLoading(true);
      try {
        const data = await apiFetch<{ templates: any[] }>(
          "/api/strategies/templates",
          { cacheTtlMs: 30_000 },
        );
        if (!cancelled) setTemplates(data.templates ?? []);
      } catch {
        if (!cancelled) setTemplates([]);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  // ---- Client-side filtering ----
  const filtered = useMemo(() => {
    let list = templates;

    if (typeFilter !== "all") {
      list = list.filter((t) => t.strategy_type === typeFilter);
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (t) =>
          (t.name ?? "").toLowerCase().includes(q) ||
          (t.description ?? "").toLowerCase().includes(q),
      );
    }

    return list;
  }, [templates, typeFilter, search]);

  // ---- Use template handler ----
  const handleUseTemplate = (template: any) => {
    const config = template.config_json || {};
    const store = useBuilderStore.getState();

    store.setField("name", config.name || template.name || "");
    store.setField("description", config.description || template.description || "");
    store.setField("action", config.action || "BUY");
    store.setField("timeframe", config.timeframe || "1D");
    store.setField("symbols", config.symbols || []);
    store.setField("stopLoss", config.stopLossPct || 3);
    store.setField("takeProfit", config.takeProfitPct || 8);
    store.setField("positionSize", config.positionPct || 5);
    store.setField("strategyType", "custom");

    // Try to load conditions via loadFromSpec if the config matches StrategySpec shape
    try {
      const parsed = parseStrategySpec(JSON.stringify(config));
      if (parsed.ok) {
        store.loadFromSpec(parsed.spec);
      }
    } catch {
      // silently ignore — fields were already set above
    }

    // Switch to AI mode so user can refine with Cerberus
    onModeSwitch("ai");
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full">
      {/* ---- Filter bar ---- */}
      <div className="flex items-center gap-3 border-b border-border p-4">
        <select
          className="app-select text-sm"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="all">All Types</option>
          <option value="momentum">Momentum</option>
          <option value="mean_reversion">Mean Reversion</option>
          <option value="breakout">Breakout</option>
          <option value="trend">Trend</option>
        </select>

        <input
          className="app-input text-sm flex-1"
          placeholder="Search templates..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* ---- Card grid ---- */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="app-card p-4 animate-pulse space-y-3"
              >
                <div className="h-4 bg-muted rounded w-2/3" />
                <div className="h-3 bg-muted rounded w-full" />
                <div className="h-3 bg-muted rounded w-1/2" />
                <div className="h-8 bg-muted rounded w-full mt-2" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            No templates found
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4">
            {filtered.map((template) => (
              <div
                key={template.id ?? template.name}
                className="app-card p-4 hover:border-blue-500/50 transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-sm">{template.name}</h3>
                  <span
                    className={`app-pill text-xs px-2 py-0.5 rounded-full ${typeBadgeClass(template.strategy_type)}`}
                  >
                    {template.strategy_type}
                  </span>
                </div>

                <p className="text-xs text-muted-foreground line-clamp-2 mb-3">
                  {template.description ||
                    template.config_json?.overview ||
                    ""}
                </p>

                <div className="flex flex-wrap gap-1 mb-3">
                  {(template.config_json?.featureSignals || []).map(
                    (sig: string) => (
                      <span key={sig} className="app-pill text-xs">
                        {sig.toUpperCase()}
                      </span>
                    ),
                  )}
                </div>

                <button
                  className="app-button-secondary w-full text-xs"
                  onClick={() => handleUseTemplate(template)}
                >
                  Use Template
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
