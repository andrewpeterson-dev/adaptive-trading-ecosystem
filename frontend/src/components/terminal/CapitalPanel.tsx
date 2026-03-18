"use client";
import { useState, useCallback, useEffect } from "react";
import { DollarSign, Pencil, Check, X, Sparkles, Shield, Brain, Zap } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import { updateBotCapital, updateAiCapitalManagement } from "@/lib/cerberus-api";
import { apiFetch } from "@/lib/api/client";
import type { BotDetail } from "@/lib/cerberus-api";

interface CapitalPanelProps {
  detail: BotDetail;
  onDetailUpdate?: (updates: Partial<BotDetail>) => void;
}

type OverrideLevel = "advisory" | "soft" | "full";

const OVERRIDE_OPTIONS: { value: OverrideLevel; label: string; icon: typeof Shield; color: string; desc: string }[] = [
  { value: "advisory", label: "Advisory", icon: Shield, color: "text-sky-400", desc: "AI logs only" },
  { value: "soft", label: "Guided", icon: Brain, color: "text-violet-400", desc: "Can delay or reduce size" },
  { value: "full", label: "Full Auto", icon: Zap, color: "text-amber-400", desc: "Can cancel, reduce, or exit" },
];

export function CapitalPanel({ detail, onDetailUpdate }: CapitalPanelProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);

  // Derive override level from the current version (syncs on refresh/re-fetch)
  const versionData = detail.currentVersion as Record<string, unknown> | null;
  const serverOverride = (versionData?.overrideLevel as OverrideLevel | undefined) ?? "soft";
  const [overrideLevel, setOverrideLevel] = useState<OverrideLevel>(serverOverride);
  const [overrideSaving, setOverrideSaving] = useState(false);

  // Re-sync when the detail prop updates (e.g. after page refresh or 30s polling)
  useEffect(() => {
    setOverrideLevel(serverOverride);
  }, [serverOverride]);

  const handleEdit = () => { setInput(detail.allocatedCapital ? String(detail.allocatedCapital) : ""); setIsEditing(true); };
  const handleSave = async () => {
    setSaving(true);
    try {
      const parsed = input.trim() ? parseFloat(input.replace(/[,$]/g, "")) : null;
      const value = parsed && !isNaN(parsed) && parsed > 0 ? parsed : null;
      await updateBotCapital(detail.id, value);
      onDetailUpdate?.({ allocatedCapital: value });
      setIsEditing(false);
    } catch (err) {
      console.error("Capital update failed:", err);
    } finally { setSaving(false); }
  };

  const handleToggleAi = async () => {
    const v = !detail.aiCapitalManagement;
    try {
      await updateAiCapitalManagement(detail.id, v);
      onDetailUpdate?.({ aiCapitalManagement: v });
    } catch (err) {
      console.error("AI capital management toggle failed:", err);
    }
  };

  const handleOverrideChange = useCallback(async (level: OverrideLevel) => {
    setOverrideSaving(true);
    const prev = overrideLevel;
    setOverrideLevel(level);
    try {
      await apiFetch(`/api/ai/tools/bots/${detail.id}/override-level`, {
        method: "PATCH",
        body: JSON.stringify({ override_level: level }),
      });
    } catch (err) {
      console.error("Override level update failed:", err);
      setOverrideLevel(prev);
    } finally {
      setOverrideSaving(false);
    }
  }, [detail.id, overrideLevel]);

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
    </TerminalPanel>
  );
}
