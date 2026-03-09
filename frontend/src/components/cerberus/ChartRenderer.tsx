'use client';

import type { ChartSpec } from '@/types/cerberus';

interface ChartRendererProps {
  spec: ChartSpec;
}

export function ChartRenderer({ spec }: ChartRendererProps) {
  // Simplified chart rendering -- uses CSS bars for basic visualization
  // For production, integrate lightweight-charts or Recharts here
  const maxY = Math.max(...spec.series.flatMap(s => s.data.map(d => d.y)), 1);

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-3">
      <h4 className="text-xs font-semibold text-foreground mb-2">{spec.title}</h4>
      <div className="space-y-2">
        {spec.series.map((series) => (
          <div key={series.name}>
            <span className="text-xs text-muted-foreground">{series.name}</span>
            <div className="flex items-end gap-px h-16 mt-1">
              {series.data.slice(-30).map((point, i) => (
                <div
                  key={i}
                  className="flex-1 rounded-t-sm"
                  style={{
                    height: `${(point.y / maxY) * 100}%`,
                    backgroundColor: series.color || 'hsl(var(--primary))',
                    minHeight: '2px',
                    opacity: 0.6 + (i / series.data.length) * 0.4,
                  }}
                  title={`${point.x}: ${point.y}`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
