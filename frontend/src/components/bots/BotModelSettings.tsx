"use client";

import { useState, useEffect } from "react";
import { Cpu, Zap } from "lucide-react";
import { updateBotModel, toggleAutoRoute } from "@/lib/cerberus-api";

const AI_MODELS = [
  { value: "gpt-5.4", label: "GPT-5.4" },
  { value: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { value: "gpt-4.1", label: "GPT-4.1 (Fast)" },
  { value: "deepseek-r1", label: "DeepSeek R1" },
];

interface BotModelSettingsProps {
  botId: string;
  currentModel: string;
  autoRouteEnabled: boolean;
  onUpdate?: () => void;
}

export function BotModelSettings({
  botId,
  currentModel,
  autoRouteEnabled: initialAutoRoute,
  onUpdate,
}: BotModelSettingsProps) {
  const [model, setModel] = useState(currentModel);
  const [autoRoute, setAutoRoute] = useState(initialAutoRoute);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setModel(currentModel);
    setAutoRoute(initialAutoRoute);
  }, [currentModel, initialAutoRoute]);

  const handleModelChange = async (newModel: string) => {
    setSaving(true);
    try {
      await updateBotModel(botId, newModel);
      setModel(newModel);
      onUpdate?.();
    } catch {
      // revert on failure
      setModel(model);
    } finally {
      setSaving(false);
    }
  };

  const handleAutoRouteToggle = async () => {
    setSaving(true);
    try {
      const newVal = !autoRoute;
      await toggleAutoRoute(botId, newVal);
      setAutoRoute(newVal);
      onUpdate?.();
    } catch {
      // revert on failure
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="app-panel p-4">
      <div className="flex items-center gap-2 mb-3">
        <Cpu className="h-4 w-4 text-violet-400" />
        <h3 className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          AI Model
        </h3>
      </div>

      <div className="space-y-3">
        <div>
          <label className="app-label mb-1.5 block text-[11px]">Primary Model</label>
          <select
            value={model}
            onChange={(e) => handleModelChange(e.target.value)}
            disabled={saving || autoRoute}
            className="app-select text-sm"
          >
            {AI_MODELS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          {autoRoute && (
            <p className="mt-1 text-[10px] text-muted-foreground">
              Auto-routing active — model selected automatically
            </p>
          )}
        </div>

        <label className="flex items-center gap-3 cursor-pointer group">
          <div className="relative">
            <input
              type="checkbox"
              checked={autoRoute}
              onChange={handleAutoRouteToggle}
              disabled={saving}
              className="peer sr-only"
            />
            <div className="h-5 w-9 rounded-full border border-border/60 bg-muted/30 transition-colors peer-checked:border-violet-400/40 peer-checked:bg-violet-400/20" />
            <div className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-muted-foreground/60 transition-all peer-checked:translate-x-4 peer-checked:bg-violet-400" />
          </div>
          <div>
            <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors flex items-center gap-1.5">
              <Zap className="h-3 w-3" /> Auto-Optimize Model
            </span>
            <p className="text-[10px] text-muted-foreground/70">
              Automatically switch to the best-performing model
            </p>
          </div>
        </label>
      </div>
    </div>
  );
}
