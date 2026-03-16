"use client";
import { Activity } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import type { BotDetail } from "@/lib/cerberus-api";

interface MarketContextPanelProps {
  vixLevel?: number;
  detail: BotDetail;
}

function deriveSpyTrend(detail: BotDetail): { label: string; color: string } {
  const spyTrades = detail.trades.filter(
    (t) => t.symbol.toUpperCase() === "SPY" && t.status === "closed" && t.netPnl != null,
  );
  if (spyTrades.length === 0) return { label: "Analyzing...", color: "text-muted-foreground" };

  const recentTrades = spyTrades.slice(-5);
  const avgPnl = recentTrades.reduce((sum, t) => sum + (t.netPnl ?? 0), 0) / recentTrades.length;

  if (avgPnl > 0) return { label: "Bullish \u2191", color: "text-emerald-400" };
  if (avgPnl < 0) return { label: "Bearish \u2193", color: "text-rose-400" };
  return { label: "Sideways \u2194", color: "text-amber-400" };
}

function deriveVixInfo(vix: number | undefined): { label: string; color: string } {
  if (vix == null) return { label: "N/A", color: "text-muted-foreground" };
  if (vix < 15) return { label: `${vix.toFixed(1)} (Low)`, color: "text-emerald-400" };
  if (vix < 20) return { label: `${vix.toFixed(1)} (Normal)`, color: "text-emerald-400" };
  if (vix < 30) return { label: `${vix.toFixed(1)} (Elevated)`, color: "text-amber-400" };
  return { label: `${vix.toFixed(1)} (High)`, color: "text-rose-400" };
}

function deriveSentiment(vix: number | undefined): { label: string; color: string } {
  if (vix == null) return { label: "N/A", color: "text-muted-foreground" };
  if (vix < 20) return { label: "Risk-On", color: "text-emerald-400" };
  if (vix <= 30) return { label: "Neutral", color: "text-amber-400" };
  return { label: "Risk-Off", color: "text-rose-400" };
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-border/30 last:border-0">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`text-xs font-semibold font-mono ${color ?? "text-foreground"}`}>{value}</span>
    </div>
  );
}

export function MarketContextPanel({ vixLevel, detail }: MarketContextPanelProps) {
  const spyTrend = deriveSpyTrend(detail);
  const vixInfo = deriveVixInfo(vixLevel);
  const sentiment = deriveSentiment(vixLevel);

  return (
    <TerminalPanel title="Market Context" icon={<Activity className="h-3.5 w-3.5" />} accent="text-cyan-400" compact>
      <Row label="SPY Trend" value={spyTrend.label} color={spyTrend.color} />
      <Row label="VIX" value={vixInfo.label} color={vixInfo.color} />
      <Row label="Sentiment" value={sentiment.label} color={sentiment.color} />
      <Row label="Events" value="No events scheduled" color="text-muted-foreground" />
    </TerminalPanel>
  );
}
