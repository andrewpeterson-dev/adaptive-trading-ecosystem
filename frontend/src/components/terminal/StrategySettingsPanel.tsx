"use client";
import { Settings2 } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import { formatTimeframe, humanizeLabel, summarizeRisk } from "@/lib/bot-visualization";

interface StrategySettingsPanelProps {
  config: Record<string, unknown>;
  strategyType: string;
}

function Cell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl bg-muted/20 px-3 py-2">
      <div className="text-[9px] text-muted-foreground/70 uppercase tracking-wider">{label}</div>
      <div className={`text-sm font-semibold mt-0.5 ${color ?? "text-foreground"}`}>{value}</div>
    </div>
  );
}

export function StrategySettingsPanel({ config, strategyType }: StrategySettingsPanelProps) {
  const risk = summarizeRisk(config);
  const riskColor = risk === "Conservative" ? "text-emerald-400" : risk === "Moderate" ? "text-amber-400" : "text-rose-400";
  const mode = strategyType === "ai_generated" ? "AI Assisted" : strategyType === "custom" ? "Custom" : "Manual";

  return (
    <TerminalPanel title="Bot Settings" icon={<Settings2 className="h-3.5 w-3.5" />} accent="text-sky-400" compact>
      <div className="grid grid-cols-2 gap-2">
        <Cell label="Strategy mode" value={mode} />
        <Cell label="Timeframe" value={formatTimeframe(config.timeframe)} />
        <Cell label="Market bias" value={(config.action as string) === "SELL" ? "Short" : "Long"} color={(config.action as string) === "SELL" ? "text-rose-400" : "text-emerald-400"} />
        <Cell label="Risk profile" value={risk} color={riskColor} />
      </div>
    </TerminalPanel>
  );
}
