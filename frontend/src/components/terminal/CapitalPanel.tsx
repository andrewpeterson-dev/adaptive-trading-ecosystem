"use client";
import { useState, useCallback, useEffect } from "react";
import { DollarSign, Pencil, Check, X, Sparkles, Shield, Brain, Zap, AlertCircle } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import { updateBotCapital, updateAiCapitalManagement } from "@/lib/cerberus-api";
import { apiFetch, ApiError } from "@/lib/api/client";
import type { BotDetail } from "@/lib/cerberus-api";

interface CapitalPanelProps {
  detail: BotDetail;
  onDetailUpdate?: (updates: Partial<BotDetail>) => void;
}

type OverrideLevel = "advisory" | "soft" | "full";

const AGGRESSIVENESS_LEVELS = [
  { value: 1, label: "Conservative", color: "bg-green-400", desc: "Strict conditions, smaller positions" },
  { value: 2, label: "Moderate", color: "bg-blue-400", desc: "Balanced risk/reward" },
  { value: 3, label: "Aggressive", color: "bg-amber-400", desc: "Relaxed conditions, larger positions" },
  { value: 4, label: "Very Aggressive", color: "bg-red-400", desc: "Loose triggers, maximum sizing" },
];

const OVERRIDE_OPTIONS: { value: OverrideLevel; label: string; icon: typeof Shield; color: string; desc: string }[] = [
  { value: "advisory", label: "Advisory", icon: Shield, color: "text-sky-400", desc: "AI logs only" },
  { value: "soft", label: "Guided", icon: Brain, color: "text-violet-400", desc: "Can delay or reduce size" },
  { value: "full", label: "Full Auto", icon: Zap, color: "text-amber-400", desc: "AI makes all trading decisions" },
];

export function CapitalPanel({ detail, onDetailUpdate }: CapitalPanelProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);

  // Derive override level — check ai_brain_config first, then version override
  const versionData = detail.currentVersion as Record<string, unknown> | null;
  const aiBrainConfig = detail.aiBrainConfig;
  const aiBrainMode = aiBrainConfig?.execution_mode as string | undefined;

  // If ai_brain_config says ai_driven, override level is "full"
  const serverOverride: OverrideLevel = aiBrainMode === "ai_driven"
    ? "full"
    : aiBrainMode === "ai_assisted"
    ? "soft"
    : (detail.overrideLevel as OverrideLevel | undefined) ?? (versionData?.overrideLevel as OverrideLevel | undefined) ?? "soft";

  const [overrideLevel, setOverrideLevel] = useState<OverrideLevel>(serverOverride);
  const [overrideSaving, setOverrideSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Aggressiveness
  const serverAggressiveness = detail.aggressiveness ?? 2;
  const [aggressiveness, setAggressiveness] = useState(serverAggressiveness);
  const [aggSaving, setAggSaving] = useState(false);

  useEffect(() => {
    setOverrideLevel(serverOverride);
  }, [serverOverride]);

  useEffect(() => {
    setAggressiveness(serverAggressiveness);
  }, [serverAggressiveness]);

  const handleEdit = () => { setInput(detail.allocatedCapital ? String(detail.allocatedCapital) : ""); setIsEditing(true); };
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const parsed = input.trim() ? parseFloat(input.replace(/[,$]/g, "")) : null;
      const value = parsed && !isNaN(parsed) && parsed > 0 ? parsed : null;
      await updateBotCapital(detail.id, value);
      onDetailUpdate?.({ allocatedCapital: value });
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save capital");
    } finally { setSaving(false); }
  };

  const handleToggleAi = async () => {
    const v = !detail.aiCapitalManagement;
    setError(null);
    try {
      await updateAiCapitalManagement(detail.id, v);
      onDetailUpdate?.({ aiCapitalManagement: v });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to toggle AI capital");
    }
  };

  const handleAggressivenessChange = useCallback(async (level: number) => {
    setAggSaving(true);
    const prev = aggressiveness;
    setAggressiveness(level);
    try {
      await apiFetch(`/api/ai/tools/bots/${detail.id}/aggressiveness`, {
        method: "PATCH",
        body: JSON.stringify({ aggressiveness: level }),
      });
      onDetailUpdate?.({ aggressiveness: level } as Partial<BotDetail>);
    } catch (err) {
      console.error("Aggressiveness update failed:", err);
      setAggressiveness(prev);
      setError(err instanceof ApiError && err.status === 401 ? "Session expired — please log in again" : "Save failed");
    } finally {
      setAggSaving(false);
    }
  }, [detail.id, aggressiveness, onDetailUpdate]);

  const handleOverrideChange = useCallback(async (level: OverrideLevel) => {
    setOverrideSaving(true);
    setError(null);
    const prev = overrideLevel;
    setOverrideLevel(level);
    try {
      await apiFetch(`/api/ai/tools/bots/${detail.id}/override-level`, {
        method: "PATCH",
        body: JSON.stringify({ override_level: level }),
      });
      if (level === "full" || prev === "full") {
        const newMode = level === "full" ? "ai_driven" : level === "soft" ? "ai_assisted" : "manual";
        await apiFetch(`/api/ai/tools/bots/${detail.id}/ai-config`, {
          method: "PATCH",
          body: JSON.stringify({ execution_mode: newMode }),
        });
        // Update parent state so the derived serverOverride stays consistent
        const updatedBrainConfig = { ...(detail.aiBrainConfig || {}), execution_mode: newMode };
        onDetailUpdate?.({ overrideLevel: level, aiBrainConfig: updatedBrainConfig } as Partial<BotDetail>);
      } else {
        onDetailUpdate?.({ overrideLevel: level } as Partial<BotDetail>);
      }
    } catch (err) {
      console.error("Override level update failed:", err);
      setOverrideLevel(prev);
      setError(err instanceof ApiError && err.status === 401 ? "Session expired — please log in again" : "Save failed");
    } finally {
      setOverrideSaving(false);
    }
  }, [detail.id, detail.aiBrainConfig, overrideLevel, onDetailUpdate]);

  // Show AI Brain model info when in full auto mode
  const modelConfig = aiBrainConfig?.model_config as Record<string, unknown> | undefined;
  const modelName = modelConfig?.primary_model as string | undefined;

  return (
    <TerminalPanel
      title="Capital & AI"
      icon={<DollarSign className="h-3.5 w-3.5" />}
      accent="text-emerald-400"
      compact
      actions={!isEditing ? <button type="button" onClick={handleEdit} aria-label="Edit capital" className="p-1 text-muted-foreground hover:text-foreground transition-colors"><Pencil className="h-3 w-3" /></button> : undefined}
    >
      {/* ── Capital Amount ── */}
      {isEditing ? (
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">$</span>
          <input type="text" inputMode="decimal" value={input} onChange={(e) => setInput(e.target.value)} placeholder="25000" aria-label="Capital amount" className="app-input flex-1 text-sm" autoFocus onKeyDown={(e) => { if (e.key === "Enter") handleSave(); if (e.key === "Escape") setIsEditing(false); }} />
          <button type="button" onClick={handleSave} disabled={saving} aria-label="Save capital" className="p-1 text-emerald-400 hover:bg-emerald-400/10 rounded-full"><Check className="h-4 w-4" /></button>
          <button type="button" onClick={() => setIsEditing(false)} aria-label="Cancel editing" className="p-1 text-muted-foreground hover:bg-muted/60 rounded-full"><X className="h-4 w-4" /></button>
        </div>
      ) : (
        <div className="text-center">
          <div className="text-2xl font-bold text-foreground font-mono">
            {detail.allocatedCapital ? `$${detail.allocatedCapital.toLocaleString()}` : "Full Account"}
          </div>
          <div className="text-[10px] text-muted-foreground mt-0.5">
            {detail.allocatedCapital ? "Allocated to this bot" : "Using broker equity"}
          </div>
        </div>
      )}

      {/* ── AI Capital Sizing Toggle ── */}
      <div className="mt-3 flex items-center justify-between rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3 w-3 text-violet-400" />
          <span className="text-[11px] text-muted-foreground">AI capital sizing</span>
        </div>
        <button
          type="button"
          onClick={handleToggleAi}
          aria-label={detail.aiCapitalManagement ? "Disable AI capital management" : "Enable AI capital management"}
          className={`relative h-5 w-9 rounded-full transition-colors ${detail.aiCapitalManagement ? "bg-violet-500" : "bg-muted-foreground/30"}`}
        >
          <span className={`absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${detail.aiCapitalManagement ? "translate-x-4" : "translate-x-0"}`} />
        </button>
      </div>

      {/* ── AI Autonomy Level ── */}
      <div className="mt-3">
        <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
          AI Autonomy
        </div>
        <div className="space-y-1">
          {OVERRIDE_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            const selected = overrideLevel === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => handleOverrideChange(opt.value)}
                disabled={overrideSaving}
                className={`w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-all ${
                  selected
                    ? "bg-foreground/[0.06] border border-border/60"
                    : "border border-transparent hover:bg-muted/20"
                } disabled:opacity-50`}
              >
                <div className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md ${selected ? "bg-foreground/10" : ""}`}>
                  <Icon className={`h-3 w-3 ${selected ? opt.color : "text-muted-foreground/50"}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`text-[11px] font-semibold ${selected ? "text-foreground" : "text-muted-foreground"}`}>
                    {opt.label}
                  </div>
                  <div className="text-[9px] text-muted-foreground/70 leading-tight">
                    {opt.desc}
                  </div>
                </div>
                {selected && (
                  <div className={`h-1.5 w-1.5 shrink-0 rounded-full ${opt.color.replace("text-", "bg-")}`} />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Aggressiveness ── */}
      <div className="mt-3">
        <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-1.5">
          Aggressiveness
        </div>
        <div className="flex gap-1">
          {AGGRESSIVENESS_LEVELS.map((level) => {
            const selected = aggressiveness === level.value;
            return (
              <button
                key={level.value}
                type="button"
                onClick={() => handleAggressivenessChange(level.value)}
                disabled={aggSaving}
                title={`${level.label}: ${level.desc}`}
                className={`flex-1 flex flex-col items-center gap-1 rounded-lg px-1 py-1.5 transition-all ${
                  selected
                    ? "bg-foreground/[0.06] border border-border/60"
                    : "border border-transparent hover:bg-muted/20"
                } disabled:opacity-50`}
              >
                <div className={`h-2 w-2 rounded-full ${selected ? level.color : "bg-muted-foreground/30"}`} />
                <div className={`text-[8px] font-medium leading-tight text-center ${selected ? "text-foreground" : "text-muted-foreground/60"}`}>
                  {level.label}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── AI Brain Model Info (when Full Auto) ── */}
      {overrideLevel === "full" && modelName && (
        <div className="mt-2 rounded-lg border border-border/40 bg-muted/10 px-3 py-2">
          <div className="text-[9px] font-semibold uppercase tracking-[0.18em] text-muted-foreground mb-1">
            AI Brain
          </div>
          <div className="text-[11px] text-foreground font-medium">{modelName}</div>
          {Array.isArray(aiBrainConfig?.data_sources) && (
            <div className="text-[9px] text-muted-foreground mt-0.5">
              Sources: {(aiBrainConfig.data_sources as string[]).join(", ")}
            </div>
          )}
        </div>
      )}

      {/* ── Error display ── */}
      {error && (
        <div className="mt-2 flex items-center gap-2 rounded-lg border border-red-400/30 bg-red-400/8 px-3 py-2 text-[11px] text-red-400">
          <AlertCircle className="h-3 w-3 shrink-0" />
          {error}
          <button type="button" onClick={() => setError(null)} className="ml-auto text-red-400/60 hover:text-red-400">
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
    </TerminalPanel>
  );
}
