"use client";
import { ShieldAlert } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import { formatPercent } from "@/lib/bot-visualization";

interface RiskMetricsPanelProps {
  config: Record<string, unknown>;
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-xs font-semibold font-mono ${color ?? "text-foreground"}`}>{value}</span>
    </div>
  );
}

export function RiskMetricsPanel({ config }: RiskMetricsPanelProps) {
  const posSize = formatPercent(config.position_size_pct as number | null | undefined, 1, true);
  const sl = formatPercent(config.stop_loss_pct as number | null | undefined, 1, true);
  const tp = formatPercent(config.take_profit_pct as number | null | undefined, 1, true);
  const commish = formatPercent(config.commission_pct as number | null | undefined, 2, true);
  const slip = formatPercent(config.slippage_pct as number | null | undefined, 2, true);
  const maxLoss = formatPercent(config.max_loss_pct as number | null | undefined, 1, true);

  return (
    <TerminalPanel title="Risk & Sizing" icon={<ShieldAlert className="h-3.5 w-3.5" />} accent="text-amber-400" compact>
      <Row label="Position size" value={posSize} />
      <Row label="Stop loss" value={sl} color="text-rose-400" />
      <Row label="Take profit" value={tp} color="text-emerald-400" />
      <Row label="Trading costs" value={`${commish} + ${slip}`} />
      <Row label="Max daily loss" value={maxLoss} />
      {typeof config.max_trades_per_day === "number" && config.max_trades_per_day > 0 && (
        <Row label="Max trades/day" value={String(config.max_trades_per_day)} />
      )}
      {typeof config.cooldown_bars === "number" && config.cooldown_bars > 0 && (
        <Row label="Cooldown bars" value={String(config.cooldown_bars)} />
      )}
    </TerminalPanel>
  );
}
