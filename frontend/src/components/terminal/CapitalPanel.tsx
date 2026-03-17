"use client";
import { useState } from "react";
import { DollarSign, Pencil, Check, X, Sparkles } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import { updateBotCapital, updateAiCapitalManagement } from "@/lib/cerberus-api";
import type { BotDetail } from "@/lib/cerberus-api";

interface CapitalPanelProps {
  detail: BotDetail;
  onDetailUpdate?: (updates: Partial<BotDetail>) => void;
}

export function CapitalPanel({ detail, onDetailUpdate }: CapitalPanelProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);

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
    try { await updateAiCapitalManagement(detail.id, v); onDetailUpdate?.({ aiCapitalManagement: v }); } catch (err) {
      console.error("AI capital management toggle failed:", err);
    }
  };

  return (
    <TerminalPanel
      title="Capital"
      icon={<DollarSign className="h-3.5 w-3.5" />}
      accent="text-emerald-400"
      compact
      actions={!isEditing ? <button type="button" onClick={handleEdit} aria-label="Edit capital" className="p-1 text-muted-foreground hover:text-foreground transition-colors"><Pencil className="h-3 w-3" /></button> : undefined}
    >
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
          <div className="text-[10px] text-muted-foreground mt-1">
            {detail.allocatedCapital ? "Allocated to this bot" : "Using broker equity"}
          </div>
        </div>
      )}
      <div className="mt-3 flex items-center justify-between rounded-xl border border-border/40 bg-muted/10 px-3 py-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3 w-3 text-violet-400" />
          <span className="text-[11px] text-muted-foreground">AI managed</span>
        </div>
        <button type="button" onClick={handleToggleAi} className={`relative h-4.5 w-8 rounded-full transition-colors ${detail.aiCapitalManagement ? "bg-violet-500" : "bg-muted-foreground/30"}`}>
          <span className={`absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white shadow-sm transition-transform ${detail.aiCapitalManagement ? "translate-x-4" : "translate-x-0.5"}`} />
        </button>
      </div>
    </TerminalPanel>
  );
}
