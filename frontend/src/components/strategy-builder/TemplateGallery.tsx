"use client";

import { useEffect, useMemo, useState } from "react";
import { useBuilderStore } from "@/stores/builder-store";
import { apiFetch } from "@/lib/api/client";
import { Clock, Target, Shield, TrendingUp, Search, Layers } from "lucide-react";

interface TemplateGalleryProps {
  onModeSwitch: (mode: "ai" | "manual" | "template") => void;
}

interface TemplateData {
  id: number;
  name: string;
  description: string;
  strategy_type: string;
  timeframe: string;
  action: string;
  symbols: string[];
  conditions: Array<Record<string, unknown>>;
  condition_groups: Array<Record<string, unknown>>;
  stop_loss_pct: number;
  take_profit_pct: number;
  position_size_pct: number;
  trailing_stop_pct: number | null;
  config_json: Record<string, unknown>;
  is_system: boolean;
}

const TYPE_COLORS: Record<string, string> = {
  momentum: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
  mean_reversion: "bg-purple-500/15 text-purple-400 border-purple-500/20",
  breakout: "bg-blue-500/15 text-blue-400 border-blue-500/20",
  trend: "bg-amber-500/15 text-amber-400 border-amber-500/20",
  scalping: "bg-rose-500/15 text-rose-400 border-rose-500/20",
  options: "bg-cyan-500/15 text-cyan-400 border-cyan-500/20",
};

const TYPE_LABELS: Record<string, string> = {
  momentum: "Momentum",
  mean_reversion: "Mean Reversion",
  breakout: "Breakout",
  trend: "Trend Following",
  scalping: "Scalping",
  options: "Options",
};

function typeBadgeClass(type: string): string {
  return TYPE_COLORS[type] ?? "bg-zinc-500/15 text-zinc-400 border-zinc-500/20";
}

function extractIndicators(conditions: Array<Record<string, unknown>>): string[] {
  const seen = new Set<string>();
  const indicators: string[] = [];
  for (const c of conditions) {
    const ind = String(c.indicator || "").toUpperCase();
    if (ind && !seen.has(ind)) {
      seen.add(ind);
      indicators.push(ind);
    }
  }
  return indicators;
}

export default function TemplateGallery({ onModeSwitch }: TemplateGalleryProps) {
  const [templates, setTemplates] = useState<TemplateData[]>([]);
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setIsLoading(true);
      setLoadError(null);
      try {
        const data = await apiFetch<{ templates: TemplateData[] }>(
          "/api/strategies/templates",
          { cacheTtlMs: 30_000 },
        );
        if (!cancelled) setTemplates(data.templates ?? []);
      } catch (err) {
        if (!cancelled) {
          setTemplates([]);
          setLoadError(err instanceof Error ? err.message : "Failed to load templates");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const availableTypes = useMemo(() => {
    const types = new Set(templates.map(t => t.strategy_type));
    return Array.from(types).sort();
  }, [templates]);

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

  const handleUseTemplate = (template: TemplateData) => {
    const store = useBuilderStore.getState();
    store.reset();

    // Load all fields from the template
    store.setField("name", template.name || "");
    store.setField("description", template.description || "");
    store.setField("action", (template.action || "BUY") as "BUY" | "SELL");
    store.setField("timeframe", template.timeframe || "1D");
    store.setField("symbols", template.symbols || ["SPY"]);
    store.setField("stopLoss", (template.stop_loss_pct || 0.02) * 100);
    store.setField("takeProfit", (template.take_profit_pct || 0.05) * 100);
    store.setField("positionSize", (template.position_size_pct || 0.05) * 100);
    store.setField("strategyType", "custom");

    // Load condition groups if available
    if (template.condition_groups && template.condition_groups.length > 0) {
      store.setField("conditionGroups", template.condition_groups as any);
    } else if (template.conditions && template.conditions.length > 0) {
      // Wrap flat conditions into a single group
      store.setField("conditionGroups", [{
        id: "A",
        conditions: template.conditions.map((c, i) => ({
          id: `t_${i}`,
          indicator: String(c.indicator || ""),
          operator: String(c.operator || ">"),
          value: Number(c.value || 0),
          params: (c.params || {}) as Record<string, number>,
          action: String(c.action || "BUY"),
          compare_to: c.compare_to as string | undefined,
        })),
        joiner: "AND",
      }] as any);
    }

    if (template.trailing_stop_pct != null && template.trailing_stop_pct > 0) {
      store.setField("trailingStopEnabled", true);
      store.setField("trailingStop", template.trailing_stop_pct * 100);
    }

    // Set AI context if available
    if (template.config_json && Object.keys(template.config_json).length > 0) {
      store.setField("aiContext", template.config_json as any);
    }

    onModeSwitch("manual");
  };

  // Render
  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 pt-6 pb-4 space-y-4">
        <div>
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-400" />
            Strategy Templates
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Start with a proven template, then customize to your needs
          </p>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              className="app-input pl-9 text-sm w-full"
              placeholder="Search templates..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="app-select text-sm"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="all">All Types</option>
            {availableTypes.map(t => (
              <option key={t} value={t}>{TYPE_LABELS[t] || t}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Card grid */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        {loadError ? (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <div className="w-12 h-12 rounded-xl bg-red-500/10 flex items-center justify-center mb-3">
              <Search className="w-5 h-5 text-red-400" />
            </div>
            <p className="text-sm text-red-400">Failed to load templates</p>
            <p className="text-xs text-muted-foreground/60 mt-1">{loadError}</p>
          </div>
        ) : isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="app-card p-5 animate-pulse space-y-3">
                <div className="h-4 bg-muted rounded w-2/3" />
                <div className="h-3 bg-muted rounded w-full" />
                <div className="h-3 bg-muted rounded w-1/2" />
                <div className="flex gap-2 mt-2">
                  <div className="h-6 bg-muted rounded-full w-16" />
                  <div className="h-6 bg-muted rounded-full w-16" />
                </div>
                <div className="h-9 bg-muted rounded-xl w-full mt-3" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center">
            <div className="w-12 h-12 rounded-xl bg-muted/30 flex items-center justify-center mb-3">
              <Search className="w-5 h-5 text-muted-foreground" />
            </div>
            <p className="text-sm text-muted-foreground">No templates found</p>
            <p className="text-xs text-muted-foreground/60 mt-1">Try adjusting your search or filter</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.map((template) => {
              const indicators = extractIndicators(template.conditions || []);
              return (
                <div
                  key={template.id ?? template.name}
                  className="app-card p-5 hover:border-blue-500/40 transition-all group cursor-pointer"
                  onClick={() => handleUseTemplate(template)}
                >
                  {/* Header */}
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-semibold text-sm text-foreground leading-tight pr-2">{template.name}</h3>
                    <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full border font-medium ${typeBadgeClass(template.strategy_type)}`}>
                      {TYPE_LABELS[template.strategy_type] || template.strategy_type}
                    </span>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-muted-foreground line-clamp-2 mb-3 leading-relaxed">
                    {template.description}
                  </p>

                  {/* Indicators */}
                  {indicators.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {indicators.map((ind) => (
                        <span key={ind} className="app-pill text-[10px] font-mono">
                          {ind}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Stats row */}
                  <div className="grid grid-cols-3 gap-2 mb-4">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      <span>{template.timeframe}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-red-400/80">
                      <Shield className="w-3 h-3" />
                      <span>{(template.stop_loss_pct * 100).toFixed(1)}% SL</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs text-emerald-400/80">
                      <Target className="w-3 h-3" />
                      <span>{(template.take_profit_pct * 100).toFixed(1)}% TP</span>
                    </div>
                  </div>

                  {/* Symbols */}
                  <div className="flex items-center gap-1.5 mb-4">
                    {(template.symbols || []).slice(0, 4).map((s) => (
                      <span key={s} className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-md bg-primary/10 text-primary border border-primary/20">
                        {s}
                      </span>
                    ))}
                    {(template.symbols || []).length > 4 && (
                      <span className="text-[10px] text-muted-foreground">+{template.symbols.length - 4}</span>
                    )}
                  </div>

                  {/* CTA */}
                  <button
                    className="app-button-secondary w-full text-xs group-hover:border-blue-500/40 group-hover:text-blue-400 transition-colors"
                    onClick={(e) => { e.stopPropagation(); handleUseTemplate(template); }}
                  >
                    Use This Template
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
