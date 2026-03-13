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
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

function getRiskLevel(summary: RiskSummaryExtended): {
  label: string;
  variant: "success" | "warning" | "danger";
} {
  if (summary.is_halted) return { label: "Halted", variant: "danger" };
  const drawdownRatio =
    summary.max_drawdown_limit > 0
      ? summary.current_drawdown_pct / summary.max_drawdown_limit
      : 0;
  if (drawdownRatio > 0.8) return { label: "Critical", variant: "danger" };
  if (drawdownRatio > 0.5) return { label: "Elevated", variant: "warning" };
  return { label: "Contained", variant: "success" };
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
      const query = `?mode=${mode}`;
      const [riskRes, eventsRes] = await Promise.allSettled([
        apiFetch<RiskSummaryExtended>(`/api/trading/risk-summary${query}`),
        apiFetch<{ events?: RiskEvent[] }>(`/api/trading/risk-events${query}`),
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
      await apiFetch("/api/trading/resume-trading", { method: "POST" });
      await fetchAll();
    } finally {
      setResuming(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !risk) {
    return (
      <EmptyState
        icon={<Unplug className="h-5 w-5 text-muted-foreground" />}
        title="No risk data available"
        description="Connect a broker and start the backend to view drawdown controls, event logs, and trading halts."
      />
    );
  }

  const riskLevel = risk ? getRiskLevel(risk) : null;
  const gauges: RiskGaugeConfig[] = risk
    ? [
        {
          label: "Drawdown",
          current: risk.current_drawdown_pct ?? 0,
          limit: risk.max_drawdown_limit ?? 0.15,
          unit: "%",
        },
        {
          label: "Open Positions",
          current: risk.open_positions ?? 0,
          limit: 20,
          unit: "positions",
        },
        {
          label: "Trades / Hour",
          current: (risk.trades_last_hour ?? (risk as any).trades_this_hour) ?? 0,
          limit: (risk as any).max_trades_per_hour ?? 30,
          unit: "trades",
        },
      ]
    : [];

  return (
    <div className="app-page">
      <SubNav items={[
        { href: "/dashboard", label: "Overview" },
        { href: "/portfolio", label: "Portfolio" },
        { href: "/risk", label: "Risk" },
      ]} />

      <PageHeader
        eyebrow="Protection"
        title="Risk Monitoring"
        description="Stay ahead of drawdown limits, monitor operational halts, and inspect every recorded risk event in one terminal-grade console."
        badge={
          riskLevel ? <Badge variant={riskLevel.variant}>{riskLevel.label}</Badge> : undefined
        }
        meta={
          <>
            <Badge variant="neutral">{mode === "live" ? "Live" : "Paper"}</Badge>
            {lastRefresh && (
              <Badge variant="neutral" className="tracking-normal font-mono">
                Updated {lastRefresh.toLocaleTimeString()}
              </Badge>
            )}
          </>
        }
        actions={
          <Button onClick={fetchAll} variant="secondary" size="sm">
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      {risk && (
        <div className="app-panel p-5 sm:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex items-start gap-3">
              {risk.is_halted ? (
                <ShieldAlert className="mt-1 h-5 w-5 text-red-300" />
              ) : (
                <ShieldCheck className="mt-1 h-5 w-5 text-emerald-300" />
              )}
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-semibold">
                    {risk.is_halted ? "Trading Halted" : "Trading Active"}
                  </h2>
                  {riskLevel && <Badge variant={riskLevel.variant}>{riskLevel.label}</Badge>}
                </div>
                {risk.halt_reason && (
                  <p className="text-sm text-red-300">{risk.halt_reason}</p>
                )}
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  {(risk.peak_equity ?? 0) > 0 && (
                    <Badge variant="neutral" className="tracking-normal">
                      Peak Equity ${(risk.peak_equity ?? 0).toLocaleString()}
                    </Badge>
                  )}
                  {(risk.open_positions ?? null) !== null && (
                    <Badge variant="neutral" className="tracking-normal">
                      {risk.open_positions} open position
                      {risk.open_positions !== 1 ? "s" : ""}
                    </Badge>
                  )}
                  {(risk.recent_risk_events ?? null) !== null && (
                    <Badge variant="neutral" className="tracking-normal">
                      {risk.recent_risk_events} recent events
                    </Badge>
                  )}
                </div>
              </div>
            </div>

            {risk.is_halted && (
              <Button onClick={handleResume} disabled={resuming} variant="success" size="sm">
                {resuming ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                Resume Trading
              </Button>
            )}
          </div>
        </div>
      )}

      {gauges.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {gauges.map((gauge) => (
            <RiskGauge key={gauge.label} config={gauge} />
          ))}
        </div>
      )}

      <RiskEventLog events={events} />
    </div>
  );
}
