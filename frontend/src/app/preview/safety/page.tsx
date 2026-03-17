"use client";

import {
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  BarChart3,
  Activity,
  ToggleLeft,
  Zap,
  TrendingDown,
  Lock,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";

// ---------------------------------------------------------------------------
// MOCK DATA — no API calls
// ---------------------------------------------------------------------------

const DAILY_DRAWDOWN = -2.8; // percent
const WEEKLY_DRAWDOWN = -4.2; // percent

const DRAWDOWN_TIERS = [
  { tier: 1, threshold: -2, label: "Reduce sizes 50%", color: "amber" },
  { tier: 2, threshold: -4, label: "Halt new entries", color: "orange" },
  { tier: 3, threshold: -7, label: "Daily kill switch", color: "red" },
  { tier: 4, threshold: -10, label: "Weekly kill switch", color: "rose" },
];

const STRATEGY_SCORES = [
  {
    key: "momentum",
    label: "Momentum",
    score: 78,
    trades: 45,
    winRate: 62,
    roi: 12.4,
    blocked: false,
  },
  {
    key: "mean_reversion",
    label: "Mean Reversion",
    score: 64,
    trades: 32,
    winRate: 55,
    roi: 4.1,
    blocked: false,
  },
  {
    key: "breakout",
    label: "Breakout",
    score: 23,
    trades: 18,
    winRate: 38,
    roi: -8.2,
    blocked: true,
  },
  {
    key: "ai_generated",
    label: "AI Generated",
    score: 71,
    trades: 28,
    winRate: 60,
    roi: 9.7,
    blocked: false,
  },
];

const SECTOR_ALLOCATIONS = [
  { sector: "Technology", pct: 28, nearCap: true },
  { sector: "Healthcare", pct: 15, nearCap: false },
  { sector: "Financials", pct: 12, nearCap: false },
  { sector: "Energy", pct: 8, nearCap: false },
  { sector: "Consumer", pct: 5, nearCap: false },
];

const CAP_PCT = 30;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreColor(score: number) {
  if (score >= 70) return { bar: "bg-emerald-500", text: "text-emerald-400" };
  if (score >= 30) return { bar: "bg-amber-500", text: "text-amber-400" };
  return { bar: "bg-red-500", text: "text-red-400" };
}

function tierColors(color: string) {
  const map: Record<string, { bg: string; border: string; text: string; dot: string }> = {
    amber: {
      bg: "bg-amber-500/10",
      border: "border-amber-500/30",
      text: "text-amber-400",
      dot: "bg-amber-500",
    },
    orange: {
      bg: "bg-orange-500/10",
      border: "border-orange-500/30",
      text: "text-orange-400",
      dot: "bg-orange-500",
    },
    red: {
      bg: "bg-red-500/10",
      border: "border-red-500/30",
      text: "text-red-400",
      dot: "bg-red-500",
    },
    rose: {
      bg: "bg-rose-900/30",
      border: "border-rose-700/40",
      text: "text-rose-400",
      dot: "bg-rose-600",
    },
  };
  return map[color] ?? map["amber"];
}

// Clamp drawdown value to a 0-100 scale mapped to 0% → -10%
function drawdownToPercent(dd: number): number {
  // dd is negative, e.g. -2.8. Map -10 → 100%, 0 → 0%
  return Math.min(100, Math.max(0, (Math.abs(dd) / 10) * 100));
}

function activeTier(dd: number) {
  const abs = Math.abs(dd);
  if (abs >= 10) return 4;
  if (abs >= 7) return 3;
  if (abs >= 4) return 2;
  if (abs >= 2) return 1;
  return 0;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SectionCard({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-border/60 bg-card shadow-sm overflow-hidden ${className}`}
    >
      {children}
    </div>
  );
}

function SectionHeader({
  icon,
  title,
  right,
}: {
  icon: React.ReactNode;
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-5 py-4 border-b border-border/50">
      <div className="flex items-center gap-2.5">
        <span className="text-muted-foreground">{icon}</span>
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section 1: Graduated Drawdown Monitor
// ---------------------------------------------------------------------------

function DrawdownMonitor() {
  const dailyTier = activeTier(DAILY_DRAWDOWN);
  const dailyBarPct = drawdownToPercent(DAILY_DRAWDOWN);
  const weeklyBarPct = drawdownToPercent(WEEKLY_DRAWDOWN);

  const activeTierData = dailyTier > 0 ? DRAWDOWN_TIERS[dailyTier - 1] : null;

  return (
    <SectionCard>
      <SectionHeader
        icon={<TrendingDown className="h-4 w-4" />}
        title="Graduated Drawdown Monitor"
        right={
          dailyTier > 0 && activeTierData ? (
            <Badge variant="warning">
              Tier {dailyTier} Active
            </Badge>
          ) : (
            <Badge variant="success">All Clear</Badge>
          )
        }
      />

      <div className="p-5 space-y-6">
        {/* Current readings */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-border/50 bg-surface-1/50 p-4">
            <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground mb-1">
              Daily Drawdown
            </p>
            <p className="text-2xl font-bold text-amber-400 tabular-nums">
              {DAILY_DRAWDOWN}%
            </p>
            <p className="text-[11px] text-amber-400/70 mt-1">Tier 1 — Sizes reduced 50%</p>
          </div>
          <div className="rounded-lg border border-border/50 bg-surface-1/50 p-4">
            <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground mb-1">
              Weekly Drawdown
            </p>
            <p className="text-2xl font-bold text-orange-400 tabular-nums">
              {WEEKLY_DRAWDOWN}%
            </p>
            <p className="text-[11px] text-orange-400/70 mt-1">Approaching Tier 2 threshold</p>
          </div>
        </div>

        {/* Progress bars with zone markers */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground mb-1">
            <span>Daily — {Math.abs(DAILY_DRAWDOWN)}% of 10% max</span>
            <span className="tabular-nums">{DAILY_DRAWDOWN}%</span>
          </div>

          {/* Track */}
          <div className="relative h-3 rounded-full bg-muted/50 overflow-hidden">
            {/* Zone segments */}
            <div className="absolute inset-y-0 left-0 w-[20%] bg-amber-500/20" />
            <div className="absolute inset-y-0 left-[20%] w-[20%] bg-orange-500/20" />
            <div className="absolute inset-y-0 left-[40%] w-[30%] bg-red-500/20" />
            <div className="absolute inset-y-0 left-[70%] right-0 bg-rose-900/40" />
            {/* Fill */}
            <div
              className="absolute inset-y-0 left-0 bg-amber-500 rounded-full transition-all"
              style={{ width: `${dailyBarPct}%` }}
            />
          </div>

          {/* Tick labels */}
          <div className="relative h-4">
            {DRAWDOWN_TIERS.map((t) => {
              const pos = (Math.abs(t.threshold) / 10) * 100;
              return (
                <div
                  key={t.tier}
                  className="absolute -translate-x-1/2 text-[10px] text-muted-foreground"
                  style={{ left: `${pos}%` }}
                >
                  {t.threshold}%
                </div>
              );
            })}
          </div>
        </div>

        {/* Weekly bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[11px] text-muted-foreground mb-1">
            <span>Weekly — {Math.abs(WEEKLY_DRAWDOWN)}% of 10% max</span>
            <span className="tabular-nums">{WEEKLY_DRAWDOWN}%</span>
          </div>
          <div className="relative h-3 rounded-full bg-muted/50 overflow-hidden">
            <div className="absolute inset-y-0 left-0 w-[20%] bg-amber-500/20" />
            <div className="absolute inset-y-0 left-[20%] w-[20%] bg-orange-500/20" />
            <div className="absolute inset-y-0 left-[40%] w-[30%] bg-red-500/20" />
            <div className="absolute inset-y-0 left-[70%] right-0 bg-rose-900/40" />
            <div
              className="absolute inset-y-0 left-0 bg-orange-500 rounded-full transition-all"
              style={{ width: `${weeklyBarPct}%` }}
            />
          </div>
        </div>

        {/* Tier legend */}
        <div className="grid grid-cols-2 gap-2">
          {DRAWDOWN_TIERS.map((t) => {
            const c = tierColors(t.color);
            const isActive = activeTier(DAILY_DRAWDOWN) === t.tier;
            return (
              <div
                key={t.tier}
                className={`flex items-start gap-2.5 rounded-lg border p-3 transition-colors ${
                  isActive
                    ? `${c.bg} ${c.border}`
                    : "border-border/40 bg-transparent opacity-60"
                }`}
              >
                <div className={`mt-1 h-2 w-2 rounded-full shrink-0 ${c.dot}`} />
                <div>
                  <p className={`text-[11px] font-semibold ${isActive ? c.text : "text-muted-foreground"}`}>
                    Tier {t.tier} — {t.threshold}%
                  </p>
                  <p className="text-[10px] text-muted-foreground leading-4">{t.label}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Section 2: Kill Switch Control
// ---------------------------------------------------------------------------

function KillSwitchPanel() {
  const isActive = false; // kill switch is OFF — bots are running

  return (
    <SectionCard>
      <SectionHeader
        icon={<Zap className="h-4 w-4" />}
        title="Kill Switch Control"
        right={<Badge variant="neutral">Manual</Badge>}
      />

      <div className="p-5 space-y-5">
        {/* Big toggle area */}
        <div
          className={`flex items-center justify-between rounded-xl border p-5 ${
            isActive
              ? "border-red-500/30 bg-red-500/8"
              : "border-emerald-500/25 bg-emerald-500/8"
          }`}
        >
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              {isActive ? (
                <ShieldAlert className="h-5 w-5 text-red-400" />
              ) : (
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
              )}
              <p
                className={`text-base font-semibold ${
                  isActive ? "text-red-300" : "text-emerald-300"
                }`}
              >
                {isActive ? "All bot trading is HALTED" : "All bot trading is ACTIVE"}
              </p>
            </div>
            <p className="text-[12px] text-muted-foreground pl-7">
              3 running bots would be paused
            </p>
          </div>

          {/* Display-only toggle */}
          <div className="relative shrink-0">
            <div
              className={`h-8 w-14 rounded-full border transition-colors ${
                isActive
                  ? "border-red-500/40 bg-red-500/20"
                  : "border-emerald-500/30 bg-emerald-500/15"
              }`}
            >
              <div
                className={`absolute top-1 h-6 w-6 rounded-full shadow transition-all ${
                  isActive
                    ? "left-7 bg-red-400"
                    : "left-1 bg-emerald-400"
                }`}
              />
            </div>
          </div>
        </div>

        {/* Meta info */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-border/40 bg-muted/20 p-3.5">
            <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              Status
            </p>
            <div className="mt-1.5 flex items-center gap-1.5">
              <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <p className="text-sm font-medium text-emerald-400">Running</p>
            </div>
          </div>
          <div className="rounded-lg border border-border/40 bg-muted/20 p-3.5">
            <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              Last Triggered
            </p>
            <p className="mt-1.5 text-sm font-medium text-foreground">Never</p>
          </div>
          <div className="rounded-lg border border-border/40 bg-muted/20 p-3.5">
            <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              Active Bots
            </p>
            <p className="mt-1.5 text-sm font-medium text-foreground">3</p>
          </div>
          <div className="rounded-lg border border-border/40 bg-muted/20 p-3.5">
            <p className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
              Mode
            </p>
            <p className="mt-1.5 text-sm font-medium text-foreground">Paper</p>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
          <Lock className="h-3 w-3 shrink-0" />
          Kill switch can be triggered manually or fires automatically at Tier 3/4 drawdown thresholds.
        </p>
      </div>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Section 3: Category / Strategy Scoring
// ---------------------------------------------------------------------------

function StrategyScoring() {
  return (
    <SectionCard>
      <SectionHeader
        icon={<Activity className="h-4 w-4" />}
        title="Strategy Category Scoring"
        right={
          <span className="text-[11px] text-muted-foreground">
            Blocked below 30 / 100
          </span>
        }
      />

      <div className="divide-y divide-border/40">
        {STRATEGY_SCORES.map((s) => {
          const c = scoreColor(s.score);
          return (
            <div key={s.key} className="px-5 py-4">
              <div className="flex items-center justify-between mb-2.5">
                <div className="flex items-center gap-2">
                  <p
                    className={`text-sm font-semibold ${
                      s.blocked ? "line-through text-muted-foreground" : "text-foreground"
                    }`}
                  >
                    {s.label}
                  </p>
                  {s.blocked && (
                    <span className="inline-flex items-center rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-red-400">
                      Blocked
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  {/* Score pill */}
                  <span
                    className={`text-sm font-bold tabular-nums ${c.text}`}
                  >
                    {s.score}
                    <span className="text-[10px] font-normal text-muted-foreground">
                      /100
                    </span>
                  </span>
                </div>
              </div>

              {/* Score bar */}
              <div className="h-1.5 rounded-full bg-muted/50 overflow-hidden mb-3">
                <div
                  className={`h-full rounded-full ${c.bar} transition-all`}
                  style={{ width: `${s.score}%` }}
                />
              </div>

              {/* Stats row */}
              <div className="flex items-center gap-4 text-[11px] text-muted-foreground">
                <span>{s.trades} trades</span>
                <span className="h-3 w-px bg-border/60" />
                <span>{s.winRate}% win rate</span>
                <span className="h-3 w-px bg-border/60" />
                <span
                  className={
                    s.roi >= 0 ? "text-emerald-400" : "text-red-400"
                  }
                >
                  {s.roi >= 0 ? "+" : ""}
                  {s.roi}% ROI
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Section 4: Sector Concentration
// ---------------------------------------------------------------------------

function SectorConcentration() {
  const maxBarWidth = 100; // visual 100% = CAP_PCT (30%)

  return (
    <SectionCard>
      <SectionHeader
        icon={<BarChart3 className="h-4 w-4" />}
        title="Sector Concentration"
        right={
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-muted/30 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Cap: {CAP_PCT}%
          </span>
        }
      />

      <div className="p-5 space-y-4">
        {/* Column headers */}
        <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-widest text-muted-foreground px-0">
          <span>Sector</span>
          <span>Allocation vs {CAP_PCT}% cap</span>
        </div>

        <div className="space-y-3">
          {SECTOR_ALLOCATIONS.map((s) => {
            const barFill = (s.pct / CAP_PCT) * maxBarWidth; // scale so 30% = full bar
            const capLinePos = 100; // cap is always at right edge
            const isNearCap = s.pct >= CAP_PCT * 0.8;

            return (
              <div key={s.sector} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-foreground">{s.sector}</span>
                    {isNearCap && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400">
                        <AlertTriangle className="h-2.5 w-2.5" />
                        Near Cap
                      </span>
                    )}
                  </div>
                  <span
                    className={`text-sm font-semibold tabular-nums ${
                      isNearCap ? "text-amber-400" : "text-foreground"
                    }`}
                  >
                    {s.pct}%
                  </span>
                </div>

                {/* Bar track with cap line */}
                <div className="relative h-2.5 rounded-full bg-muted/50 overflow-hidden">
                  {/* Cap zone marker */}
                  <div className="absolute inset-y-0 right-0 w-px bg-border/80" />
                  {/* Fill */}
                  <div
                    className={`h-full rounded-full transition-all ${
                      isNearCap ? "bg-amber-500" : "bg-blue-500"
                    }`}
                    style={{ width: `${Math.min(barFill, 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-5 pt-2 text-[11px] text-muted-foreground border-t border-border/40">
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-4 rounded-sm bg-blue-500" />
            <span>Within limit</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-4 rounded-sm bg-amber-500" />
            <span>Near cap (&ge;80%)</span>
          </div>
          <div className="flex items-center gap-1.5 ml-auto">
            <div className="h-3 w-px bg-border" />
            <span>30% cap threshold</span>
          </div>
        </div>
      </div>
    </SectionCard>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SafetyPreviewPage() {
  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Risk Management"
        title="Safety Dashboard"
        description="Graduated drawdown protection, kill switch control, strategy quality gates, and sector concentration limits — all in one view."
        badge={<Badge variant="warning">Preview — Mock Data</Badge>}
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <DrawdownMonitor />
        <KillSwitchPanel />
        <StrategyScoring />
        <SectorConcentration />
      </div>
    </div>
  );
}
