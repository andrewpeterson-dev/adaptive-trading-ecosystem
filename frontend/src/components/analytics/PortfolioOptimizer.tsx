"use client";

import React, { useState, useCallback } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  Loader2,
  Sparkles,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  Target,
  AlertTriangle,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Surface, SurfaceBody, SurfaceHeader, SurfaceTitle } from "@/components/ui/surface";
import { PIE_COLORS } from "@/lib/utils";

const METHODS = [
  { value: "max_sharpe", label: "Max Sharpe Ratio" },
  { value: "min_volatility", label: "Min Volatility" },
  { value: "hrp", label: "Hierarchical Risk Parity" },
  { value: "risk_parity", label: "Risk Parity" },
];

interface OptimizationResult {
  weights: Record<string, number>;
  expected_return: number;
  volatility: number;
  sharpe: number;
  method: string;
}

interface FrontierPoint {
  expected_return: number;
  volatility: number;
  sharpe: number;
}

interface RebalanceOrder {
  ticker: string;
  action: string;
  shares: number;
  estimated_cost: number;
  reason: string;
  current_weight: number;
  target_weight: number;
  weight_delta: number;
  is_tax_loss_harvest: boolean;
}

interface RebalancePlan {
  orders: RebalanceOrder[];
  total_portfolio_value: number;
  cash_available: number;
  estimated_total_cost: number;
  num_buys: number;
  num_sells: number;
  tax_loss_harvest_count: number;
}

export function PortfolioOptimizer() {
  const [tickers, setTickers] = useState("SPY,QQQ,IWM,TLT,GLD,VNQ");
  const [method, setMethod] = useState("max_sharpe");
  const [maxWeight, setMaxWeight] = useState(0.25);
  const [lookbackDays, setLookbackDays] = useState(252);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptimizationResult | null>(null);
  const [frontierData, setFrontierData] = useState<FrontierPoint[]>([]);
  const [frontierLoading, setFrontierLoading] = useState(false);
  const [rebalancePlan, setRebalancePlan] = useState<RebalancePlan | null>(null);
  const [rebalanceLoading, setRebalanceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runOptimization = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setFrontierData([]);
    setRebalancePlan(null);

    const tickerList = tickers
      .split(",")
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);

    if (tickerList.length < 2) {
      setError("Enter at least 2 ticker symbols separated by commas.");
      setLoading(false);
      return;
    }

    try {
      const data = await apiFetch<OptimizationResult>("/api/portfolio/optimize", {
        method: "POST",
        body: JSON.stringify({
          tickers: tickerList,
          method,
          lookback_days: lookbackDays,
          constraints: { max_weight: maxWeight, min_weight: 0 },
        }),
        cacheTtlMs: 0,
      });
      setResult(data);

      // Also fetch frontier data
      setFrontierLoading(true);
      try {
        const frontier = await apiFetch<{ points: FrontierPoint[] }>(
          `/api/portfolio/efficient-frontier?tickers=${tickerList.join(",")}&lookback_days=${lookbackDays}&n_points=40`,
          { cacheTtlMs: 0 }
        );
        setFrontierData(frontier.points || []);
      } catch {
        // Frontier is non-critical
      } finally {
        setFrontierLoading(false);
      }
    } catch (e: any) {
      setError(e?.message || "Optimization failed. Check your tickers and try again.");
    } finally {
      setLoading(false);
    }
  }, [tickers, method, maxWeight, lookbackDays]);

  const generateRebalancePlan = useCallback(async () => {
    setRebalanceLoading(true);
    setError(null);
    try {
      const plan = await apiFetch<RebalancePlan>(
        `/api/portfolio/rebalance-plan?method=${method}&lookback_days=${lookbackDays}&max_weight=${maxWeight}`,
        { cacheTtlMs: 0 }
      );
      setRebalancePlan(plan);
    } catch (e: any) {
      setError(e?.message || "Failed to generate rebalance plan. Make sure you have Webull positions.");
    } finally {
      setRebalanceLoading(false);
    }
  }, [method, lookbackDays, maxWeight]);

  // Prepare pie chart data from result
  const pieData = result
    ? Object.entries(result.weights)
        .filter(([, w]) => w > 0.001)
        .map(([ticker, weight]) => ({ name: ticker, value: weight * 100 }))
        .sort((a, b) => b.value - a.value)
    : [];

  return (
    <div className="space-y-5">
      {/* Optimizer Controls */}
      <Surface>
        <SurfaceHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Portfolio Optimizer</SurfaceTitle>
          </div>
        </SurfaceHeader>
        <SurfaceBody>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Tickers */}
            <div className="sm:col-span-2 lg:col-span-4">
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5 block">
                Tickers (comma-separated)
              </label>
              <input
                type="text"
                value={tickers}
                onChange={(e) => setTickers(e.target.value)}
                placeholder="SPY, QQQ, IWM, TLT, GLD"
                className="w-full rounded-lg border border-border/75 bg-card px-3 py-2 text-sm font-mono placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-ring/50"
              />
            </div>

            {/* Method */}
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5 block">
                Method
              </label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="w-full rounded-lg border border-border/75 bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/50"
              >
                {METHODS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>

            {/* Max Weight */}
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5 block">
                Max Weight
              </label>
              <input
                type="number"
                value={maxWeight}
                onChange={(e) => setMaxWeight(parseFloat(e.target.value) || 0.25)}
                min={0.05}
                max={1.0}
                step={0.05}
                className="w-full rounded-lg border border-border/75 bg-card px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/50"
              />
            </div>

            {/* Lookback */}
            <div>
              <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5 block">
                Lookback (days)
              </label>
              <input
                type="number"
                value={lookbackDays}
                onChange={(e) => setLookbackDays(parseInt(e.target.value, 10) || 252)}
                min={30}
                max={1260}
                step={1}
                className="w-full rounded-lg border border-border/75 bg-card px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/50"
              />
            </div>

            {/* Actions */}
            <div className="flex items-end gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={runOptimization}
                disabled={loading}
                className="flex-1"
              >
                {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                {loading ? "Optimizing..." : "Run Optimization"}
              </Button>
            </div>
          </div>

          {error && (
            <div className="mt-4 flex items-center gap-2 rounded-lg border border-red-500/25 bg-red-500/8 px-4 py-3 text-sm text-red-300">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}
        </SurfaceBody>
      </Surface>

      {/* Results */}
      {result && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {/* Pie Chart */}
          <Surface>
            <SurfaceHeader>
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-muted-foreground" />
                <SurfaceTitle>Target Allocation</SurfaceTitle>
              </div>
            </SurfaceHeader>
            <SurfaceBody>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={95}
                    paddingAngle={2}
                    label={({ name, value }) => `${name} ${value.toFixed(1)}%`}
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={entry.name} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--surface-overlay))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "16px",
                      fontSize: "12px",
                    }}
                    formatter={(val) => [`${Number(val ?? 0).toFixed(1)}%`, "Weight"]}
                  />
                  <Legend
                    verticalAlign="bottom"
                    height={36}
                    formatter={(value: string) => (
                      <span className="text-xs text-muted-foreground">{value}</span>
                    )}
                  />
                </PieChart>
              </ResponsiveContainer>
            </SurfaceBody>
          </Surface>

          {/* Metrics */}
          <div className="lg:col-span-2 space-y-4">
            <Surface>
              <SurfaceHeader>
                <SurfaceTitle>Optimization Metrics</SurfaceTitle>
              </SurfaceHeader>
              <SurfaceBody>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <MetricCard
                    label="Expected Return"
                    value={`${(result.expected_return * 100).toFixed(2)}%`}
                    positive={result.expected_return > 0}
                  />
                  <MetricCard
                    label="Volatility"
                    value={`${(result.volatility * 100).toFixed(2)}%`}
                    neutral
                  />
                  <MetricCard
                    label="Sharpe Ratio"
                    value={result.sharpe.toFixed(3)}
                    positive={result.sharpe > 0}
                  />
                  <MetricCard
                    label="Method"
                    value={METHODS.find((m) => m.value === result.method)?.label || result.method}
                    neutral
                  />
                </div>

                {/* Weight table */}
                <div className="mt-4 overflow-x-auto">
                  <table className="app-table w-full">
                    <thead>
                      <tr>
                        <th className="text-left">Ticker</th>
                        <th className="text-right">Weight</th>
                        <th className="text-right">Allocation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(result.weights)
                        .filter(([, w]) => w > 0.001)
                        .sort(([, a], [, b]) => b - a)
                        .map(([ticker, weight]) => (
                          <tr key={ticker}>
                            <td className="font-mono text-sm font-medium">{ticker}</td>
                            <td className="text-right font-mono text-sm tabular-nums">
                              {(weight * 100).toFixed(1)}%
                            </td>
                            <td className="text-right">
                              <div className="flex items-center justify-end gap-2">
                                <div className="h-1.5 w-24 rounded-full bg-muted/40 overflow-hidden">
                                  <div
                                    className="h-full rounded-full bg-blue-500"
                                    style={{ width: `${Math.min(weight * 100 * 4, 100)}%` }}
                                  />
                                </div>
                              </div>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-4 flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={generateRebalancePlan}
                    disabled={rebalanceLoading}
                  >
                    {rebalanceLoading ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <ArrowRight className="h-3.5 w-3.5" />
                    )}
                    Generate Rebalance Plan
                  </Button>
                </div>
              </SurfaceBody>
            </Surface>
          </div>
        </div>
      )}

      {/* Efficient Frontier */}
      {frontierData.length > 0 && (
        <Surface>
          <SurfaceHeader>
            <SurfaceTitle>Efficient Frontier</SurfaceTitle>
          </SurfaceHeader>
          <SurfaceBody>
            <ResponsiveContainer width="100%" height={320}>
              <ScatterChart margin={{ top: 10, right: 30, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="volatility"
                  type="number"
                  name="Volatility"
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickFormatter={(v) => `${(v * 100).toFixed(1)}%`}
                  label={{
                    value: "Volatility",
                    position: "insideBottom",
                    offset: -10,
                    style: { fontSize: 11, fill: "hsl(var(--muted-foreground))" },
                  }}
                />
                <YAxis
                  dataKey="expected_return"
                  type="number"
                  name="Return"
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickFormatter={(v) => `${(v * 100).toFixed(1)}%`}
                  label={{
                    value: "Expected Return",
                    angle: -90,
                    position: "insideLeft",
                    style: { fontSize: 11, fill: "hsl(var(--muted-foreground))" },
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--surface-overlay))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "12px",
                    fontSize: "12px",
                  }}
                  formatter={((val?: number, name?: string) => [
                    `${((val ?? 0) * 100).toFixed(2)}%`,
                    name === "expected_return" ? "Return" : name === "volatility" ? "Volatility" : name ?? "",
                  ]) as any}
                />
                <Scatter
                  data={frontierData}
                  fill="#3b82f6"
                  line={{ stroke: "#3b82f6", strokeWidth: 2 }}
                  lineType="fitting"
                >
                  {frontierData.map((_, i) => (
                    <Cell
                      key={i}
                      fill={i === frontierData.length - 1 ? "#10b981" : "#3b82f6"}
                      r={i === frontierData.length - 1 ? 6 : 3}
                    />
                  ))}
                </Scatter>
                {/* Plot the current optimization result as a star */}
                {result && (
                  <Scatter
                    data={[{ volatility: result.volatility, expected_return: result.expected_return }]}
                    fill="#f59e0b"
                    shape="star"
                    name="Optimal Portfolio"
                  />
                )}
              </ScatterChart>
            </ResponsiveContainer>
            {frontierLoading && (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            )}
          </SurfaceBody>
        </Surface>
      )}

      {/* Rebalance Plan */}
      {rebalancePlan && rebalancePlan.orders.length > 0 && (
        <Surface>
          <SurfaceHeader>
            <div className="flex items-center justify-between w-full">
              <SurfaceTitle>Rebalance Plan</SurfaceTitle>
              <div className="flex items-center gap-2">
                <Badge variant="neutral">{rebalancePlan.num_buys} buys</Badge>
                <Badge variant="neutral">{rebalancePlan.num_sells} sells</Badge>
                {rebalancePlan.tax_loss_harvest_count > 0 && (
                  <Badge variant="warning">{rebalancePlan.tax_loss_harvest_count} TLH</Badge>
                )}
              </div>
            </div>
          </SurfaceHeader>
          <SurfaceBody className="p-0">
            <div className="overflow-x-auto">
              <table className="app-table w-full">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Action</th>
                    <th className="text-right">Shares</th>
                    <th className="text-right">Current</th>
                    <th className="text-right">Target</th>
                    <th className="text-right">Est. Cost</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {rebalancePlan.orders.map((order, i) => (
                    <tr key={`${order.ticker}-${i}`}>
                      <td className="font-mono text-sm font-medium">{order.ticker}</td>
                      <td>
                        <Badge
                          variant={order.action === "buy" ? "success" : "negative"}
                          className="uppercase text-[10px]"
                        >
                          {order.action === "buy" ? (
                            <TrendingUp className="h-3 w-3" />
                          ) : (
                            <TrendingDown className="h-3 w-3" />
                          )}
                          {order.action}
                        </Badge>
                      </td>
                      <td className="text-right font-mono text-sm tabular-nums">
                        {order.shares.toFixed(2)}
                      </td>
                      <td className="text-right font-mono text-sm tabular-nums text-muted-foreground">
                        {(order.current_weight * 100).toFixed(1)}%
                      </td>
                      <td className="text-right font-mono text-sm tabular-nums">
                        {(order.target_weight * 100).toFixed(1)}%
                      </td>
                      <td className="text-right font-mono text-sm tabular-nums text-muted-foreground">
                        ${order.estimated_cost.toFixed(2)}
                      </td>
                      <td className="text-xs text-muted-foreground max-w-[200px] truncate">
                        {order.reason}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-border/50 px-4 py-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Portfolio: ${rebalancePlan.total_portfolio_value.toLocaleString()} | Cash: ${rebalancePlan.cash_available.toLocaleString()}
              </span>
              <span>
                Est. Total Cost: ${rebalancePlan.estimated_total_cost.toFixed(2)}
              </span>
            </div>
          </SurfaceBody>
        </Surface>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  positive,
  neutral,
}: {
  label: string;
  value: string;
  positive?: boolean;
  neutral?: boolean;
}) {
  return (
    <div className="rounded-lg border border-border/50 bg-muted/20 p-3">
      <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">
        {label}
      </div>
      <div
        className={`text-lg font-semibold font-mono tabular-nums ${
          neutral
            ? "text-foreground"
            : positive
            ? "text-emerald-400"
            : "text-red-400"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
