"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  Unplug,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Play,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { useTradingMode } from "@/hooks/useTradingMode";
import { RiskGauge } from "@/components/analytics/RiskGauge";
import { RiskEventLog } from "@/components/analytics/RiskEventLog";
import type { RiskEvent, RiskSummaryExtended, RiskGaugeConfig } from "@/types/risk";

function getRiskLevel(summary: RiskSummaryExtended): { label: string; color: string; bgColor: string } {
  if (summary.is_halted) return { label: "HALTED", color: "text-red-400", bgColor: "bg-red-400/10 border-red-400/30" };
  const ddRatio = summary.max_drawdown_limit > 0 ? summary.current_drawdown_pct / summary.max_drawdown_limit : 0;
  if (ddRatio > 0.8) return { label: "Critical", color: "text-red-400", bgColor: "bg-red-400/10 border-red-400/30" };
  if (ddRatio > 0.5) return { label: "High", color: "text-amber-400", bgColor: "bg-amber-400/10 border-amber-400/30" };
  if (ddRatio > 0.25) return { label: "Medium", color: "text-yellow-400", bgColor: "bg-yellow-400/10 border-yellow-400/30" };
  return { label: "Low", color: "text-emerald-400", bgColor: "bg-emerald-400/10 border-emerald-400/30" };
}

export default function RiskPage() {
  const [risk, setRisk] = useState<RiskSummaryExtended | null>(null);
  const [events, setEvents] = useState<RiskEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [resuming, setResuming] = useState(false);
  const { mode } = useTradingMode();

  const fetchAll = useCallback(async () => {
    try {
      const q = `?mode=${mode}`;
      const [riskRes, eventsRes] = await Promise.allSettled([
        apiFetch<RiskSummaryExtended>(`/api/trading/risk-summary${q}`),
        apiFetch<{ events?: RiskEvent[] }>(`/api/trading/risk-events${q}`),
      ]);

      let hasData = false;

      if (riskRes.status === "fulfilled") {
        setRisk(riskRes.value);
        hasData = true;
      }

      if (eventsRes.status === "fulfilled") {
        const data = eventsRes.value;
        setEvents((data as any).events || (data as any) || []);
        hasData = true;
      }

      if (!hasData) setError(true);
      setLastRefresh(new Date());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleResume = async () => {
    setResuming(true);
    try {
      const res = await apiFetch("/api/trading/resume-trading", { method: "POST" });
      await fetchAll();
    } finally {
      setResuming(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !risk) {
    return (
      <div className="text-center py-20 space-y-3">
        <Unplug className="h-10 w-10 text-muted-foreground/40 mx-auto" />
        <h2 className="text-lg font-semibold">No Risk Data</h2>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          Connect a broker and start the backend to view risk monitoring, drawdown gauges, and event logs.
        </p>
      </div>
    );
  }

  const riskLevel = risk ? getRiskLevel(risk) : null;

  const gauges: RiskGaugeConfig[] = risk
    ? [
        { label: "Drawdown", current: risk.current_drawdown_pct ?? 0, limit: risk.max_drawdown_limit ?? 0.15, unit: "%" },
        { label: "Open Positions", current: risk.open_positions ?? 0, limit: 20, unit: "positions" },
        { label: "Trades / Hour", current: (risk.trades_last_hour ?? (risk as any).trades_this_hour) ?? 0, limit: (risk as any).max_trades_per_hour ?? 30, unit: "trades" },
      ]
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Risk Monitoring</h2>
          {lastRefresh && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Updated {lastRefresh.toLocaleTimeString()}
            </p>
          )}
        </div>
        <button
          onClick={fetchAll}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Risk Status Summary */}
      {risk && riskLevel && (
        <div className="rounded-lg border border-border/50 bg-card p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {risk.is_halted ? (
                <ShieldAlert className="h-5 w-5 text-red-400" />
              ) : (
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
              )}
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">
                    {risk.is_halted ? "Trading Halted" : "Trading Active"}
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${riskLevel.bgColor} ${riskLevel.color}`}>
                    {riskLevel.label}
                  </span>
                </div>
                {risk.halt_reason && (
                  <p className="text-xs text-red-400 mt-0.5">{risk.halt_reason}</p>
                )}
                <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                  {(risk.peak_equity ?? 0) > 0 && <span>Peak Equity: ${(risk.peak_equity ?? 0).toLocaleString()}</span>}
                  {(risk.open_positions ?? null) !== null && <span>{risk.open_positions} open position{risk.open_positions !== 1 ? "s" : ""}</span>}
                  {(risk.recent_risk_events ?? null) !== null && <span>{risk.recent_risk_events} event{risk.recent_risk_events !== 1 ? "s" : ""}</span>}
                </div>
              </div>
            </div>
            {risk.is_halted && (
              <button
                onClick={handleResume}
                disabled={resuming}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-emerald-500 text-white text-sm font-semibold hover:bg-emerald-400 transition-colors disabled:opacity-50"
              >
                {resuming ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                Resume Trading
              </button>
            )}
          </div>
        </div>
      )}

      {/* Risk Gauges */}
      {gauges.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {gauges.map((g) => (
            <RiskGauge key={g.label} config={g} />
          ))}
        </div>
      )}

      {/* Risk Event Log */}
      <RiskEventLog events={events} />
    </div>
  );
}
