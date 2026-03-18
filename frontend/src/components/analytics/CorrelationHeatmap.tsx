"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Loader2, Grid3X3, RefreshCw } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Surface, SurfaceBody, SurfaceHeader, SurfaceTitle } from "@/components/ui/surface";

interface CorrelationData {
  tickers: string[];
  matrix: number[][];
}

function getCorrelationColor(value: number): string {
  // Diverging color scale: blue (-1) -> neutral (0) -> red (+1)
  if (value >= 0.8) return "bg-red-500/80 text-white";
  if (value >= 0.6) return "bg-red-500/50 text-red-100";
  if (value >= 0.4) return "bg-red-500/25 text-red-200";
  if (value >= 0.2) return "bg-red-500/10 text-foreground";
  if (value >= -0.2) return "bg-muted/30 text-muted-foreground";
  if (value >= -0.4) return "bg-blue-500/10 text-foreground";
  if (value >= -0.6) return "bg-blue-500/25 text-blue-200";
  if (value >= -0.8) return "bg-blue-500/50 text-blue-100";
  return "bg-blue-500/80 text-white";
}

export function CorrelationHeatmap() {
  const [tickers, setTickers] = useState("SPY,QQQ,IWM,TLT,GLD,VNQ,XLF,XLE");
  const [lookbackDays, setLookbackDays] = useState(252);
  const [data, setData] = useState<CorrelationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCorrelation = useCallback(async () => {
    const tickerList = tickers
      .split(",")
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);

    if (tickerList.length < 2) {
      setError("Enter at least 2 tickers.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await apiFetch<CorrelationData>(
        `/api/portfolio/correlation-matrix?tickers=${tickerList.join(",")}&lookback_days=${lookbackDays}`,
        { cacheTtlMs: 0 }
      );
      setData(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch correlation data.");
    } finally {
      setLoading(false);
    }
  }, [tickers, lookbackDays]);

  return (
    <Surface>
      <SurfaceHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <Grid3X3 className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Correlation Matrix</SurfaceTitle>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchCorrelation}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            {data ? "Refresh" : "Load"}
          </Button>
        </div>
      </SurfaceHeader>
      <SurfaceBody>
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1">
            <input
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              placeholder="SPY, QQQ, IWM, TLT, GLD"
              className="w-full rounded-lg border border-border/75 bg-card px-3 py-2 text-xs font-mono placeholder:text-muted-foreground/40 focus:outline-none focus:ring-2 focus:ring-ring/50"
            />
          </div>
          <div className="w-24">
            <input
              type="number"
              value={lookbackDays}
              onChange={(e) => setLookbackDays(parseInt(e.target.value, 10) || 252)}
              min={30}
              max={1260}
              className="w-full rounded-lg border border-border/75 bg-card px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-ring/50"
              title="Lookback days"
            />
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-dashed border-border/60 bg-muted/5 px-4 py-4 mb-3 text-center">
            <p className="text-xs text-muted-foreground">
              Correlation data temporarily unavailable. Adjust tickers or lookback and try again.
            </p>
          </div>
        )}

        {loading && !data && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {data && (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className="p-1.5 text-[10px] font-medium text-muted-foreground" />
                  {data.tickers.map((t) => (
                    <th
                      key={t}
                      className="p-1.5 text-[10px] font-mono font-bold text-muted-foreground text-center whitespace-nowrap"
                    >
                      {t}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.tickers.map((rowTicker, rowIdx) => (
                  <tr key={rowTicker}>
                    <td className="p-1.5 text-[10px] font-mono font-bold text-muted-foreground whitespace-nowrap">
                      {rowTicker}
                    </td>
                    {data.matrix[rowIdx].map((value, colIdx) => (
                      <td
                        key={`${rowIdx}-${colIdx}`}
                        className={`p-1.5 text-center text-[10px] font-mono tabular-nums rounded-sm ${getCorrelationColor(value)}`}
                        title={`${rowTicker} / ${data.tickers[colIdx]}: ${value.toFixed(3)}`}
                      >
                        {value.toFixed(2)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Legend */}
            <div className="mt-3 flex items-center justify-center gap-1 text-[9px] text-muted-foreground">
              <span className="px-1.5 py-0.5 rounded bg-blue-500/80 text-white">-1.0</span>
              <span className="px-1.5 py-0.5 rounded bg-blue-500/25">-0.5</span>
              <span className="px-1.5 py-0.5 rounded bg-muted/30">0.0</span>
              <span className="px-1.5 py-0.5 rounded bg-red-500/25">+0.5</span>
              <span className="px-1.5 py-0.5 rounded bg-red-500/80 text-white">+1.0</span>
            </div>
          </div>
        )}

        {!data && !loading && (
          <div className="text-center py-8 text-sm text-muted-foreground">
            Click &quot;Load&quot; to compute the correlation matrix for your tickers.
          </div>
        )}
      </SurfaceBody>
    </Surface>
  );
}
