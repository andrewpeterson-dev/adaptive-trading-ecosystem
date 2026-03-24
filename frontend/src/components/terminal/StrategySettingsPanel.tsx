"use client";
import { useState, useCallback } from "react";
import { Settings2, Pencil, Check, X, AlertCircle } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import { apiFetch } from "@/lib/api/client";
import { formatTimeframe, summarizeRisk } from "@/lib/bot-visualization";

interface StrategySettingsPanelProps {
  config: Record<string, unknown>;
  strategyType: string;
  botId?: string;
  onConfigUpdate?: (updates: Record<string, unknown>) => void;
}

const TIMEFRAMES = ["1m", "5m", "15m", "1H", "4H", "1D", "1W"];
const ACTIONS = ["BUY", "SELL"];

function Cell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl bg-muted/20 px-3 py-2">
      <div className="text-[9px] text-muted-foreground/70 uppercase tracking-wider">{label}</div>
      <div className={`text-sm font-semibold mt-0.5 ${color ?? "text-foreground"}`}>{value}</div>
    </div>
  );
}

function EditCell({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl bg-muted/20 px-3 py-2">
      <div className="text-[9px] text-muted-foreground/70 uppercase tracking-wider mb-1">{label}</div>
      {children}
    </div>
  );
}

export function StrategySettingsPanel({ config, strategyType, botId, onConfigUpdate }: StrategySettingsPanelProps) {
  const risk = summarizeRisk(config);
  const riskColor = risk === "Conservative" ? "text-emerald-400" : risk === "Moderate" ? "text-amber-400" : "text-rose-400";
  const mode = strategyType === "ai_generated" ? "AI Assisted" : strategyType === "custom" ? "Custom" : "Manual";

  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [editTimeframe, setEditTimeframe] = useState(String(config.timeframe || "1D"));
  const [editAction, setEditAction] = useState(String(config.action || "BUY"));
  const [editStopLoss, setEditStopLoss] = useState(String((Number(config.stop_loss_pct) || 0.03) * 100));
  const [editTakeProfit, setEditTakeProfit] = useState(String((Number(config.take_profit_pct) || 0.06) * 100));
  const [editPositionSize, setEditPositionSize] = useState(String(Number(config.position_size_pct) || 5));

  const startEdit = () => {
    setEditTimeframe(String(config.timeframe || "1D"));
    setEditAction(String(config.action || "BUY"));
    setEditStopLoss(String((Number(config.stop_loss_pct) || 0.03) * 100));
    setEditTakeProfit(String((Number(config.take_profit_pct) || 0.06) * 100));
    setEditPositionSize(String(Number(config.position_size_pct) || 5));
    setEditing(true);
  };

  const handleSave = useCallback(async () => {
    if (!botId) return;
    setSaving(true);
    try {
      const updatedConfig: Record<string, unknown> = {
        ...config,
        timeframe: editTimeframe,
        action: editAction,
        stop_loss_pct: parseFloat(editStopLoss) / 100,
        take_profit_pct: parseFloat(editTakeProfit) / 100,
        position_size_pct: parseFloat(editPositionSize),
      };
      await apiFetch(`/api/ai/tools/bots/${botId}/deploy`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      // Also update via modifyBot tool pattern
      await apiFetch(`/api/strategies/bot-config/${botId}`, {
        method: "PATCH",
        body: JSON.stringify(updatedConfig),
      }).catch(() => { /* endpoint may not exist for all bots */ });
      onConfigUpdate?.(updatedConfig);
      setEditing(false);
      setSaveError(null);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  }, [botId, config, editTimeframe, editAction, editStopLoss, editTakeProfit, editPositionSize, onConfigUpdate]);

  if (editing) {
    return (
      <TerminalPanel
        title="Bot Settings"
        icon={<Settings2 className="h-3.5 w-3.5" />}
        accent="text-sky-400"
        compact
        actions={
          <div className="flex items-center gap-1">
            <button type="button" onClick={handleSave} disabled={saving} aria-label="Save settings" className="p-1 text-emerald-400 hover:bg-emerald-400/10 rounded-full">
              <Check className="h-3.5 w-3.5" />
            </button>
            <button type="button" onClick={() => setEditing(false)} aria-label="Cancel" className="p-1 text-muted-foreground hover:bg-muted/60 rounded-full">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-2">
          <EditCell label="Timeframe">
            <select
              value={editTimeframe}
              onChange={(e) => setEditTimeframe(e.target.value)}
              className="w-full bg-transparent text-sm font-semibold text-foreground border-none outline-none cursor-pointer"
            >
              {TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf} className="bg-card">{formatTimeframe(tf)}</option>
              ))}
            </select>
          </EditCell>
          <EditCell label="Market bias">
            <select
              value={editAction}
              onChange={(e) => setEditAction(e.target.value)}
              className="w-full bg-transparent text-sm font-semibold text-foreground border-none outline-none cursor-pointer"
            >
              {ACTIONS.map((a) => (
                <option key={a} value={a} className="bg-card">{a === "SELL" ? "Short" : "Long"}</option>
              ))}
            </select>
          </EditCell>
          <EditCell label="Stop loss %">
            <input
              type="number"
              value={editStopLoss}
              onChange={(e) => setEditStopLoss(e.target.value)}
              step="0.5"
              min="0.5"
              max="20"
              className="w-full bg-transparent text-sm font-semibold text-foreground font-mono border-none outline-none"
            />
          </EditCell>
          <EditCell label="Take profit %">
            <input
              type="number"
              value={editTakeProfit}
              onChange={(e) => setEditTakeProfit(e.target.value)}
              step="0.5"
              min="1"
              max="50"
              className="w-full bg-transparent text-sm font-semibold text-foreground font-mono border-none outline-none"
            />
          </EditCell>
          <EditCell label="Position size %">
            <input
              type="number"
              value={editPositionSize}
              onChange={(e) => setEditPositionSize(e.target.value)}
              step="1"
              min="1"
              max="25"
              className="w-full bg-transparent text-sm font-semibold text-foreground font-mono border-none outline-none"
            />
          </EditCell>
          <Cell label="Strategy mode" value={mode} />
        </div>
        {saveError && (
          <div className="flex items-center gap-1.5 text-[11px] text-red-400 mt-2">
            <AlertCircle className="h-3 w-3 shrink-0" />
            {saveError}
          </div>
        )}
      </TerminalPanel>
    );
  }

  return (
    <TerminalPanel
      title="Bot Settings"
      icon={<Settings2 className="h-3.5 w-3.5" />}
      accent="text-sky-400"
      compact
      actions={
        botId ? (
          <button type="button" onClick={startEdit} aria-label="Edit settings" className="p-1 text-muted-foreground hover:text-foreground transition-colors">
            <Pencil className="h-3 w-3" />
          </button>
        ) : undefined
      }
    >
      <div className="grid grid-cols-2 gap-2">
        <Cell label="Strategy mode" value={mode} />
        <Cell label="Timeframe" value={formatTimeframe(config.timeframe)} />
        <Cell label="Market bias" value={(config.action as string) === "SELL" ? "Short" : "Long"} color={(config.action as string) === "SELL" ? "text-rose-400" : "text-emerald-400"} />
        <Cell label="Risk profile" value={risk} color={riskColor} />
        <Cell label="Stop loss" value={`${((Number(config.stop_loss_pct) || 0) * 100).toFixed(1)}%`} color="text-red-400" />
        <Cell label="Take profit" value={`${((Number(config.take_profit_pct) || 0) * 100).toFixed(1)}%`} color="text-emerald-400" />
      </div>
    </TerminalPanel>
  );
}
