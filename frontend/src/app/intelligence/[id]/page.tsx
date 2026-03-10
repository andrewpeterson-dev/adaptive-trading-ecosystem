"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Brain,
  ChevronDown,
  ChevronUp,
  Clock,
  Cpu,
  Play,
  Pause,
  SkipForward,
  SkipBack,
  TrendingUp,
  TrendingDown,
  Zap,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Skeleton } from "@/components/ui/skeleton";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Performance {
  sharpe: number;
  sortino: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  total_return: number;
  num_trades: number;
  confidence: number;
}

interface StrategyMeta {
  id: number;
  name: string;
  description: string | null;
  timeframe: string;
  action: string;
  stop_loss_pct: number;
  take_profit_pct: number;
  conditions: { indicator: string; operator: string; value: string | number }[];
  symbols: string[];
  created_at: string | null;
}

interface PipelineStage {
  stage: string;
  passed: boolean;
  reason: string;
}

interface IntelligenceBundle {
  strategy: StrategyMeta;
  performance: Performance;
  regime: { current: string; confidence: number };
  equity_curve: { date: string; value: number }[];
  decision_pipeline: PipelineStage[];
}

interface TradeEntry {
  id: number;
  symbol: string;
  direction: string;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  confidence: number;
  regime: string;
  signals: string[];
  approved: boolean;
  reasoning: string;
  model_name: string;
  bars_held: number | null;
}

interface ReasoningLog {
  id: number;
  timestamp: string;
  symbol: string;
  confidence: number;
  approved: boolean;
  regime: string;
  reasoning: string;
  model: string;
  latency_ms: number;
}

interface MonteCarlo {
  dates: string[];
  p5: number[];
  p25: number[];
  p50: number[];
  p75: number[];
  p95: number[];
  risk_of_ruin: number;
  expected_final: number;
  ci_90_low: number;
  ci_90_high: number;
  n_sims: number;
}

interface FeatureImportance {
  features: { feature: string; importance: number }[];
}

interface HeatmapData {
  data: { day: string; hour: number; avg_pnl_pct: number }[];
  days: string[];
  hours: number[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const REGIME_LABEL: Record<string, string> = {
  low_vol_bull: "Low-Vol Bull",
  high_vol_bull: "High-Vol Bull",
  low_vol_bear: "Low-Vol Bear",
  high_vol_bear: "High-Vol Bear",
  sideways: "Sideways",
};

const REGIME_COLOR: Record<string, string> = {
  low_vol_bull: "#10b981",
  high_vol_bull: "#f59e0b",
  low_vol_bear: "#ef4444",
  high_vol_bear: "#dc2626",
  sideways: "#6b7280",
};

function fmt(n: number, type: "pct" | "ratio" | "currency" | "int" = "ratio") {
  if (type === "pct") return `${(n * 100).toFixed(1)}%`;
  if (type === "currency") return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (type === "int") return String(Math.round(n));
  return n.toFixed(3);
}

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return iso?.slice(0, 10) ?? "";
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  sub,
  positive,
}: {
  label: string;
  value: string;
  sub?: string;
  positive?: boolean;
}) {
  const color =
    positive === undefined
      ? "text-foreground"
      : positive
      ? "text-emerald-400"
      : "text-red-400";
  return (
    <div className="rounded-xl border border-border/50 bg-card px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className={`mt-1 text-xl font-mono font-bold ${color}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

function ConfidenceGauge({ value }: { value: number }) {
  const pct = Math.min(100, Math.max(0, value));
  const color = pct >= 70 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444";
  const angle = (pct / 100) * 180 - 90; // -90 to 90 deg
  const rad = (angle * Math.PI) / 180;
  const cx = 60;
  const cy = 60;
  const r = 44;
  const nx = cx + r * Math.cos(rad);
  const ny = cy + r * Math.sin(rad);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="120" height="70" viewBox="0 0 120 70">
        <path
          d={`M 16 60 A 44 44 0 0 1 104 60`}
          fill="none"
          stroke="hsl(var(--border))"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <path
          d={`M 16 60 A 44 44 0 0 1 ${nx.toFixed(1)} ${ny.toFixed(1)}`}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
        />
        <line
          x1={cx}
          y1={cy}
          x2={nx.toFixed(1)}
          y2={ny.toFixed(1)}
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r="3" fill={color} />
        <text x={cx} y={cy + 16} textAnchor="middle" fontSize="14" fontWeight="bold" fill={color}>
          {pct.toFixed(0)}%
        </text>
      </svg>
      <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
        Confidence
      </span>
    </div>
  );
}

function PipelineFlow({ stages }: { stages: PipelineStage[] }) {
  return (
    <div className="space-y-1.5">
      {stages.map((s, i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            className={`h-5 w-5 rounded-full flex items-center justify-center shrink-0 text-[10px] font-bold ${
              s.passed
                ? "bg-emerald-400/15 text-emerald-400 border border-emerald-400/30"
                : "bg-red-400/15 text-red-400 border border-red-400/30"
            }`}
          >
            {s.passed ? "✓" : "✗"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium">{s.stage}</div>
            <div className="text-[10px] text-muted-foreground truncate">{s.reason}</div>
          </div>
          {i < stages.length - 1 && (
            <div className="absolute left-[18px] mt-5 h-1.5 w-px bg-border/50" />
          )}
        </div>
      ))}
    </div>
  );
}

function HeatmapGrid({ data, days, hours }: HeatmapData) {
  const vals = data.map((d) => d.avg_pnl_pct);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;

  const color = (v: number) => {
    const t = (v - min) / range;
    if (t > 0.6) return `rgba(16,185,129,${0.3 + t * 0.6})`;
    if (t > 0.4) return `rgba(251,191,36,${0.2 + t * 0.4})`;
    return `rgba(239,68,68,${0.2 + (1 - t) * 0.5})`;
  };

  return (
    <div className="overflow-x-auto">
      <table className="text-[10px] border-collapse w-full">
        <thead>
          <tr>
            <th className="px-2 py-1 text-muted-foreground font-normal w-8" />
            {hours.map((h) => (
              <th key={h} className="px-1 py-1 text-muted-foreground font-normal text-center">
                {h}h
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {days.map((day) => (
            <tr key={day}>
              <td className="px-2 py-0.5 text-muted-foreground">{day}</td>
              {hours.map((hour) => {
                const cell = data.find((d) => d.day === day && d.hour === hour);
                const v = cell?.avg_pnl_pct ?? 0;
                return (
                  <td
                    key={hour}
                    title={`${day} ${hour}h: ${v.toFixed(2)}%`}
                    className="px-1 py-0.5"
                  >
                    <div
                      className="w-full h-6 rounded-sm flex items-center justify-center font-mono"
                      style={{ backgroundColor: color(v) }}
                    >
                      {v > 0 ? "+" : ""}
                      {v.toFixed(1)}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MonteCarloChart({ mc }: { mc: MonteCarlo }) {
  const data = mc.dates.map((date, i) => ({
    date: date.slice(5),
    p5: mc.p5[i],
    p25: mc.p25[i],
    p50: mc.p50[i],
    p75: mc.p75[i],
    p95: mc.p95[i],
  }));

  const fmtK = (v: number) =>
    v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v.toFixed(0)}`;

  return (
    <div className="space-y-3">
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            interval={14}
          />
          <YAxis
            width={60}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={fmtK}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              fontSize: 11,
              borderRadius: 6,
            }}
            formatter={(v, name) => [fmtK(typeof v === "number" ? v : 0), String(name ?? "").toUpperCase()] as [string, string]}
          />
          <defs>
            <linearGradient id="mc95" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.12} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="mc75" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="p95" stroke="#3b82f6" fill="url(#mc95)" strokeWidth={1} strokeDasharray="4 2" />
          <Area type="monotone" dataKey="p75" stroke="#6366f1" fill="url(#mc75)" strokeWidth={1} />
          <Line type="monotone" dataKey="p50" stroke="#10b981" strokeWidth={2} dot={false} />
          <Area type="monotone" dataKey="p25" stroke="#6366f1" fill="transparent" strokeWidth={1} />
          <Area type="monotone" dataKey="p5" stroke="#3b82f6" fill="transparent" strokeWidth={1} strokeDasharray="4 2" />
        </AreaChart>
      </ResponsiveContainer>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-lg border border-border/50 bg-card px-3 py-2">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Expected Final
          </div>
          <div className="font-mono font-bold text-sm mt-0.5">
            {fmtK(mc.expected_final)}
          </div>
        </div>
        <div className="rounded-lg border border-border/50 bg-card px-3 py-2">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
            Risk of Ruin
          </div>
          <div
            className={`font-mono font-bold text-sm mt-0.5 ${
              mc.risk_of_ruin > 0.1 ? "text-red-400" : "text-emerald-400"
            }`}
          >
            {(mc.risk_of_ruin * 100).toFixed(1)}%
          </div>
        </div>
        <div className="rounded-lg border border-border/50 bg-card px-3 py-2">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
            90% CI
          </div>
          <div className="font-mono font-bold text-sm mt-0.5">
            {fmtK(mc.ci_90_low)} – {fmtK(mc.ci_90_high)}
          </div>
        </div>
      </div>
    </div>
  );
}

function TradeForensicsModal({
  trade,
  onClose,
}: {
  trade: TradeEntry;
  onClose: () => void;
}) {
  const isWin = trade.pnl > 0;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-border/60 bg-card p-6 shadow-2xl mx-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-lg font-bold">
              {trade.symbol}{" "}
              <span
                className={`text-sm font-mono ${
                  trade.direction === "long" ? "text-emerald-400" : "text-red-400"
                }`}
              >
                {trade.direction.toUpperCase()}
              </span>
            </div>
            <div className="text-xs text-muted-foreground">Trade Forensics</div>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* P&L summary */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="rounded-lg bg-muted/30 px-3 py-2 text-center">
            <div className="text-[10px] text-muted-foreground">Entry</div>
            <div className="font-mono font-bold">${trade.entry_price.toFixed(2)}</div>
          </div>
          <div className="rounded-lg bg-muted/30 px-3 py-2 text-center">
            <div className="text-[10px] text-muted-foreground">Exit</div>
            <div className="font-mono font-bold">${trade.exit_price.toFixed(2)}</div>
          </div>
          <div
            className={`rounded-lg px-3 py-2 text-center ${
              isWin ? "bg-emerald-400/10" : "bg-red-400/10"
            }`}
          >
            <div className="text-[10px] text-muted-foreground">P&L</div>
            <div className={`font-mono font-bold ${isWin ? "text-emerald-400" : "text-red-400"}`}>
              {isWin ? "+" : ""}${trade.pnl.toFixed(2)}
            </div>
          </div>
        </div>

        {/* Confidence gauge + regime */}
        <div className="flex items-center justify-between mb-4 p-3 rounded-lg bg-muted/20 border border-border/30">
          <ConfidenceGauge value={trade.confidence} />
          <div className="text-right">
            <div className="text-xs text-muted-foreground mb-1">Regime</div>
            <span
              className="text-xs font-semibold px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: `${REGIME_COLOR[trade.regime] ?? "#6b7280"}20`,
                color: REGIME_COLOR[trade.regime] ?? "#6b7280",
                border: `1px solid ${REGIME_COLOR[trade.regime] ?? "#6b7280"}40`,
              }}
            >
              {REGIME_LABEL[trade.regime] ?? trade.regime}
            </span>
          </div>
        </div>

        {/* Signals */}
        <div className="mb-3">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
            Triggered Signals
          </div>
          <div className="flex flex-wrap gap-1.5">
            {trade.signals.map((s, i) => (
              <span
                key={i}
                className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary"
              >
                {s}
              </span>
            ))}
          </div>
        </div>

        {/* AI Reasoning */}
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
            AI Reasoning
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed">{trade.reasoning}</p>
        </div>
      </div>
    </div>
  );
}

// ── Trade Replay ──────────────────────────────────────────────────────────────

function TradeReplay({ trades }: { trades: TradeEntry[] }) {
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const current = trades[idx];

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(() => {
        setIdx((i) => {
          if (i >= trades.length - 1) {
            setPlaying(false);
            return i;
          }
          return i + 1;
        });
      }, 1200);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [playing, trades.length]);

  if (!current) return null;
  const isWin = current.pnl > 0;

  return (
    <div className="rounded-xl border border-border/50 bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Trade Replay
        </div>
        <div className="text-xs text-muted-foreground">
          {idx + 1} / {trades.length}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 rounded-full bg-border/50 overflow-hidden">
        <div
          className="h-full bg-primary rounded-full transition-all duration-300"
          style={{ width: `${((idx + 1) / trades.length) * 100}%` }}
        />
      </div>

      {/* Current trade summary */}
      <div className="flex items-center justify-between">
        <div>
          <div className="font-bold text-sm">
            {current.symbol}
            <span
              className={`ml-2 text-xs font-mono ${
                current.direction === "long" ? "text-emerald-400" : "text-red-400"
              }`}
            >
              {current.direction.toUpperCase()}
            </span>
          </div>
          <div className="text-xs text-muted-foreground">{fmtDate(current.entry_time)}</div>
        </div>
        <div
          className={`font-mono font-bold text-sm ${
            isWin ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {isWin ? "+" : ""}
          {current.pnl_pct.toFixed(2)}%
        </div>
      </div>

      {/* Signals */}
      <div className="flex flex-wrap gap-1">
        {current.signals.map((s, i) => (
          <span
            key={i}
            className="text-[10px] px-1.5 py-0.5 rounded bg-muted/50 border border-border/30"
          >
            {s}
          </span>
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-3">
        <button
          onClick={() => setIdx(0)}
          className="p-1.5 rounded-lg hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
          title="Reset"
        >
          <SkipBack className="h-4 w-4" />
        </button>
        <button
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
          className="p-1.5 rounded-lg hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
        >
          ‹
        </button>
        <button
          onClick={() => setPlaying((p) => !p)}
          className="p-2 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary transition-colors"
        >
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </button>
        <button
          onClick={() => setIdx((i) => Math.min(trades.length - 1, i + 1))}
          className="p-1.5 rounded-lg hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
        >
          ›
        </button>
        <button
          onClick={() => setIdx(trades.length - 1)}
          className="p-1.5 rounded-lg hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
          title="Jump to end"
        >
          <SkipForward className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// ── Equity curve with trade markers ──────────────────────────────────────────

function EquityWithMarkers({
  curve,
  trades,
}: {
  curve: { date: string; value: number }[];
  trades: TradeEntry[];
}) {
  const isPositive = curve.length > 1 && curve[curve.length - 1].value >= curve[0].value;

  const fmtK = (v: number) =>
    v >= 1_000_000 ? `$${(v / 1_000_000).toFixed(1)}M` : `$${(v / 1000).toFixed(0)}k`;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={curve}>
        <defs>
          <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={isPositive ? "#10b981" : "#ef4444"} stopOpacity={0.25} />
            <stop offset="95%" stopColor={isPositive ? "#10b981" : "#ef4444"} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          interval="preserveStartEnd"
          tickFormatter={(d: string) => d.slice(5)}
        />
        <YAxis
          width={60}
          tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
          tickFormatter={fmtK}
        />
        <Tooltip
          contentStyle={{
            background: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            fontSize: 11,
            borderRadius: 6,
          }}
          formatter={(v) => [`$${Number(v ?? 0).toLocaleString()}`, "Equity"] as [string, string]}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke={isPositive ? "#10b981" : "#ef4444"}
          fill="url(#eqGrad)"
          strokeWidth={2}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Page loading skeleton ─────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Skeleton className="lg:col-span-2 h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type TabKey = "overview" | "trades" | "risk" | "logs";

export default function IntelligencePage() {
  const params = useParams();
  const router = useRouter();
  const strategyId = Number(params.id);

  const [tab, setTab] = useState<TabKey>("overview");
  const [bundle, setBundle] = useState<IntelligenceBundle | null>(null);
  const [trades, setTrades] = useState<TradeEntry[]>([]);
  const [logs, setLogs] = useState<ReasoningLog[]>([]);
  const [mc, setMc] = useState<MonteCarlo | null>(null);
  const [features, setFeatures] = useState<{ feature: string; importance: number }[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedTrade, setSelectedTrade] = useState<TradeEntry | null>(null);
  const [expandedLog, setExpandedLog] = useState<number | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [bundleData, tradesData, logsData, mcData, featData, hmData] =
        await Promise.all([
          apiFetch<IntelligenceBundle>(`/api/quant/strategy/${strategyId}`),
          apiFetch<{ trades: TradeEntry[] }>(`/api/quant/strategy/${strategyId}/trades`),
          apiFetch<{ logs: ReasoningLog[] }>(
            `/api/quant/strategy/${strategyId}/reasoning-logs`
          ),
          apiFetch<MonteCarlo>(`/api/quant/strategy/${strategyId}/monte-carlo`),
          apiFetch<FeatureImportance>(
            `/api/quant/strategy/${strategyId}/feature-importance`
          ),
          apiFetch<HeatmapData>(`/api/quant/strategy/${strategyId}/heatmap`),
        ]);
      setBundle(bundleData);
      setTrades(tradesData.trades ?? []);
      setLogs(logsData.logs ?? []);
      setMc(mcData);
      setFeatures(featData.features ?? []);
      setHeatmap(hmData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load intelligence data");
    } finally {
      setLoading(false);
    }
  }, [strategyId]);

  useEffect(() => {
    if (strategyId) loadAll();
  }, [strategyId, loadAll]);

  if (!strategyId || isNaN(strategyId)) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <p className="text-red-400">Invalid strategy ID.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <PageSkeleton />
      </div>
    );
  }

  if (error || !bundle) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="rounded-xl border border-red-400/20 bg-red-400/5 p-4">
          <p className="text-red-400">{error || "Strategy not found"}</p>
        </div>
        <button
          onClick={() => router.back()}
          className="mt-4 text-sm text-muted-foreground hover:text-foreground flex items-center gap-1"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
      </div>
    );
  }

  const { strategy, performance: perf, regime, equity_curve, decision_pipeline } = bundle;

  const totalReturn = perf.total_return;
  const regimeColor = REGIME_COLOR[regime.current] ?? "#6b7280";

  // Drawdown series
  const ddSeries = (() => {
    let peak = equity_curve[0]?.value ?? 0;
    return equity_curve.map((pt) => {
      if (pt.value > peak) peak = pt.value;
      return { date: pt.date, value: peak > 0 ? ((pt.value - peak) / peak) * 100 : 0 };
    });
  })();

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* ── Header ─── */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.back()}
            className="p-1.5 rounded-lg hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Brain className="h-5 w-5 text-primary" />
              {strategy.name}
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-muted-foreground">{strategy.timeframe}</span>
              <span className="h-1 w-1 rounded-full bg-muted-foreground/40" />
              <span
                className="text-xs font-mono px-1.5 py-0.5 rounded"
                style={{
                  background: `${regimeColor}15`,
                  color: regimeColor,
                  border: `1px solid ${regimeColor}30`,
                }}
              >
                {REGIME_LABEL[regime.current] ?? regime.current}
              </span>
              <span className="h-1 w-1 rounded-full bg-muted-foreground/40" />
              <Link
                href="/quant"
                className="text-xs text-primary hover:underline flex items-center gap-1"
              >
                <Zap className="h-3 w-3" /> Compare
              </Link>
            </div>
          </div>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          {strategy.symbols?.length > 0 && (
            <div className="flex gap-1 flex-wrap justify-end">
              {strategy.symbols.map((s) => (
                <span key={s} className="px-1.5 py-0.5 rounded bg-muted/40 border border-border/30">
                  {s}
                </span>
              ))}
            </div>
          )}
          {strategy.created_at && (
            <div className="mt-1">Created {fmtDate(strategy.created_at)}</div>
          )}
        </div>
      </div>

      {/* ── Metrics Bar ─── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <MetricCard
          label="Win Rate"
          value={fmt(perf.win_rate, "pct")}
          positive={perf.win_rate > 0.5}
        />
        <MetricCard
          label="Sharpe"
          value={perf.sharpe.toFixed(2)}
          sub="annualised"
          positive={perf.sharpe > 0}
        />
        <MetricCard
          label="Max Drawdown"
          value={fmt(perf.max_drawdown, "pct")}
          positive={perf.max_drawdown > -0.15}
        />
        <MetricCard
          label="Total Return"
          value={fmt(totalReturn, "pct")}
          positive={totalReturn > 0}
        />
        <MetricCard
          label="Trades"
          value={String(perf.num_trades)}
          sub={`PF: ${perf.profit_factor.toFixed(2)}`}
        />
        <MetricCard
          label="Confidence"
          value={`${perf.confidence.toFixed(0)}%`}
          positive={perf.confidence > 60}
        />
      </div>

      {/* ── Tabs ─── */}
      <div className="flex gap-1 border-b border-border/40">
        {(
          [
            { key: "overview", label: "Overview", icon: Activity },
            { key: "trades", label: "Trades", icon: TrendingUp },
            { key: "risk", label: "Risk", icon: AlertTriangle },
            { key: "logs", label: "AI Logs", icon: Brain },
          ] as { key: TabKey; label: string; icon: React.FC<{ className?: string }> }[]
        ).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
              tab === key
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* ── Overview Tab ─── */}
      {tab === "overview" && (
        <div className="space-y-6">
          {/* Main row: equity + AI panel */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Equity Curve */}
            <div className="lg:col-span-2 rounded-xl border border-border/50 bg-card p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Equity Curve
                </div>
                <span
                  className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                    totalReturn >= 0
                      ? "text-emerald-400 bg-emerald-400/10"
                      : "text-red-400 bg-red-400/10"
                  }`}
                >
                  {totalReturn >= 0 ? "+" : ""}
                  {fmt(totalReturn, "pct")}
                </span>
              </div>
              <EquityWithMarkers curve={equity_curve} trades={trades} />
            </div>

            {/* AI Intelligence Panel */}
            <div className="rounded-xl border border-border/50 bg-card p-4 space-y-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5" /> Decision Pipeline
              </div>
              <PipelineFlow stages={decision_pipeline} />
              <div className="border-t border-border/30 pt-3">
                <ConfidenceGauge value={perf.confidence} />
              </div>
              <div className="text-[10px] text-muted-foreground">
                {strategy.description || "No description provided."}
              </div>
            </div>
          </div>

          {/* Drawdown chart */}
          <div className="rounded-xl border border-border/50 bg-card p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              Drawdown — Max: {fmt(perf.max_drawdown, "pct")}
            </div>
            <ResponsiveContainer width="100%" height={100}>
              <AreaChart data={ddSeries}>
                <defs>
                  <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="date" hide />
                <YAxis tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} width={30} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    fontSize: 11,
                    borderRadius: 6,
                  }}
                  formatter={(v) => [`${Number(v ?? 0).toFixed(2)}%`, "DD"] as [string, string]}
                />
                <Area type="monotone" dataKey="value" stroke="#ef4444" fill="url(#ddGrad)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Heatmap + Feature Importance */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="rounded-xl border border-border/50 bg-card p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Profit Heatmap (hour × day)
              </div>
              {heatmap ? (
                <HeatmapGrid {...heatmap} />
              ) : (
                <Skeleton className="h-32" />
              )}
            </div>

            <div className="rounded-xl border border-border/50 bg-card p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Feature Importance
              </div>
              {features.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart
                    data={features.slice(0, 8)}
                    layout="vertical"
                    margin={{ left: 8, right: 16 }}
                  >
                    <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} />
                    <YAxis
                      type="category"
                      dataKey="feature"
                      width={100}
                      tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        fontSize: 11,
                        borderRadius: 6,
                      }}
                      formatter={(v) => [(Number(v ?? 0) * 100).toFixed(0) + "%", "Importance"] as [string, string]}
                    />
                    <Bar dataKey="importance" radius={[0, 3, 3, 0]}>
                      {features.slice(0, 8).map((_, i) => (
                        <Cell
                          key={i}
                          fill={`hsl(${220 + i * 15}, 70%, ${60 - i * 3}%)`}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Skeleton className="h-48" />
              )}
            </div>
          </div>

          {/* Monte Carlo */}
          <div className="rounded-xl border border-border/50 bg-card p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3 flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5" /> Monte Carlo Simulation
              {mc && (
                <span className="text-[10px] text-muted-foreground font-normal ml-1">
                  ({mc.n_sims} paths, 90-day horizon)
                </span>
              )}
            </div>
            {mc ? <MonteCarloChart mc={mc} /> : <Skeleton className="h-48" />}
          </div>
        </div>
      )}

      {/* ── Trades Tab ─── */}
      {tab === "trades" && (
        <div className="space-y-4">
          {trades.length > 0 && <TradeReplay trades={trades} />}

          <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/50 bg-muted/20">
                  {["Symbol", "Dir", "Entry", "Exit", "PnL", "PnL %", "Conf", "Regime", "Signals"].map(
                    (h) => (
                      <th
                        key={h}
                        className="py-2 px-3 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => {
                  const win = t.pnl > 0;
                  return (
                    <tr
                      key={t.id}
                      onClick={() => setSelectedTrade(t)}
                      className="border-b border-border/30 hover:bg-muted/20 cursor-pointer transition-colors"
                    >
                      <td className="py-2 px-3 font-bold text-xs">{t.symbol}</td>
                      <td className="py-2 px-3">
                        <span
                          className={`text-[10px] font-mono font-bold ${
                            t.direction === "long" ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {t.direction.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-xs text-muted-foreground">
                        {fmtDate(t.entry_time)}
                      </td>
                      <td className="py-2 px-3 text-xs text-muted-foreground">
                        {fmtDate(t.exit_time)}
                      </td>
                      <td
                        className={`py-2 px-3 font-mono text-xs font-medium ${
                          win ? "text-emerald-400" : "text-red-400"
                        }`}
                      >
                        {win ? "+" : ""}${t.pnl.toFixed(0)}
                      </td>
                      <td
                        className={`py-2 px-3 font-mono text-xs ${
                          win ? "text-emerald-400" : "text-red-400"
                        }`}
                      >
                        {win ? "+" : ""}
                        {t.pnl_pct.toFixed(2)}%
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`text-[10px] font-mono ${
                            t.confidence >= 70
                              ? "text-emerald-400"
                              : t.confidence >= 50
                              ? "text-amber-400"
                              : "text-red-400"
                          }`}
                        >
                          {t.confidence.toFixed(0)}%
                        </span>
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded-full"
                          style={{
                            background: `${REGIME_COLOR[t.regime] ?? "#6b7280"}15`,
                            color: REGIME_COLOR[t.regime] ?? "#6b7280",
                          }}
                        >
                          {t.regime?.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-[10px] text-muted-foreground max-w-[120px] truncate">
                        {t.signals.slice(0, 2).join(", ")}
                        {t.signals.length > 2 && ` +${t.signals.length - 2}`}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Risk Tab ─── */}
      {tab === "risk" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <MetricCard label="Stop Loss" value={fmt(strategy.stop_loss_pct, "pct")} />
            <MetricCard label="Take Profit" value={fmt(strategy.take_profit_pct, "pct")} />
            <MetricCard
              label="Risk / Reward"
              value={`1 : ${(strategy.take_profit_pct / Math.max(strategy.stop_loss_pct, 0.001)).toFixed(1)}`}
            />
          </div>

          {/* Profit Distribution */}
          {trades.length > 0 && (
            <div className="rounded-xl border border-border/50 bg-card p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                P&L Distribution
              </div>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart
                  data={(() => {
                    const buckets = Array.from({ length: 12 }, (_, i) => ({
                      label: `${(-3 + i * 0.5).toFixed(1)}%`,
                      count: 0,
                      isPos: i >= 6,
                    }));
                    trades.forEach((t) => {
                      const bi = Math.floor((t.pnl_pct + 3) / 0.5);
                      const idx = Math.max(0, Math.min(11, bi));
                      buckets[idx].count++;
                    });
                    return buckets;
                  })()}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <YAxis tick={{ fontSize: 9, fill: "hsl(var(--muted-foreground))" }} width={20} />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      fontSize: 11,
                      borderRadius: 6,
                    }}
                  />
                  <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                    {Array.from({ length: 12 }, (_, i) => (
                      <Cell key={i} fill={i >= 6 ? "#10b981" : "#ef4444"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {mc && (
            <div className="rounded-xl border border-border/50 bg-card p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Forward Risk (Monte Carlo)
              </div>
              <MonteCarloChart mc={mc} />
            </div>
          )}
        </div>
      )}

      {/* ── AI Logs Tab ─── */}
      {tab === "logs" && (
        <div className="space-y-2">
          {logs.map((log) => (
            <div
              key={log.id}
              className="rounded-xl border border-border/50 bg-card overflow-hidden"
            >
              <button
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-muted/20 transition-colors"
                onClick={() => setExpandedLog(expandedLog === log.id ? null : log.id)}
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`h-2 w-2 rounded-full shrink-0 ${
                      log.approved ? "bg-emerald-400" : "bg-red-400"
                    }`}
                  />
                  <div>
                    <div className="text-xs font-medium">
                      {log.symbol}
                      <span className="ml-2 text-[10px] text-muted-foreground">
                        via {log.model}
                      </span>
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      {fmtDate(log.timestamp)} · {log.latency_ms}ms
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${
                      log.confidence >= 70
                        ? "text-emerald-400 bg-emerald-400/10"
                        : log.confidence >= 50
                        ? "text-amber-400 bg-amber-400/10"
                        : "text-red-400 bg-red-400/10"
                    }`}
                  >
                    {log.confidence.toFixed(0)}%
                  </span>
                  <span
                    className={`text-[10px] font-medium ${
                      log.approved ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {log.approved ? "APPROVED" : "REJECTED"}
                  </span>
                  {expandedLog === log.id ? (
                    <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                </div>
              </button>
              {expandedLog === log.id && (
                <div className="px-4 pb-4 border-t border-border/30 pt-3 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                      style={{
                        background: `${REGIME_COLOR[log.regime] ?? "#6b7280"}15`,
                        color: REGIME_COLOR[log.regime] ?? "#6b7280",
                        border: `1px solid ${REGIME_COLOR[log.regime] ?? "#6b7280"}30`,
                      }}
                    >
                      {REGIME_LABEL[log.regime] ?? log.regime}
                    </span>
                    <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" /> {log.latency_ms}ms
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">{log.reasoning}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ── Trade Forensics Modal ─── */}
      {selectedTrade && (
        <TradeForensicsModal
          trade={selectedTrade}
          onClose={() => setSelectedTrade(null)}
        />
      )}
    </div>
  );
}
