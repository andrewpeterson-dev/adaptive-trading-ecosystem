"use client";

import { useEffect, useState } from "react";
import { Globe } from "lucide-react";
import { getBotUniverse, type UniverseCandidateItem } from "@/lib/reasoning-api";

export function UniverseTab({ botId }: { botId: string }) {
  const [candidates, setCandidates] = useState<UniverseCandidateItem[]>([]);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    setLoadError(false);
    getBotUniverse(botId).then(setCandidates).catch(() => setLoadError(true));
  }, [botId]);

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <Globe className="h-3.5 w-3.5 text-teal-400" />
        Universe Candidates
      </div>

      <div className="mt-4">
        {candidates.length === 0 ? (
          <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-6 text-center text-sm text-muted-foreground">
            {loadError ? "Failed to load universe data" : "No universe candidates \u2014 bot may be using fixed symbols"}
          </div>
        ) : (
          <div className="space-y-2">
            {candidates.map((c, i) => {
              const barWidth = Math.max(5, c.score * 100);
              return (
                <div
                  key={c.id}
                  className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-3"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <span className="w-6 text-right text-xs font-semibold tabular-nums text-muted-foreground">
                        #{i + 1}
                      </span>
                      <span className="font-mono text-sm font-semibold text-foreground">{c.symbol}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="h-2 w-24 overflow-hidden rounded-full bg-muted/30">
                        <div
                          className="h-full rounded-full bg-teal-400 transition-all"
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                      <span className="w-12 text-right text-xs font-semibold tabular-nums text-foreground">
                        {(c.score * 100).toFixed(0)}
                      </span>
                    </div>
                  </div>
                  {c.reason && (
                    <p className="mt-1.5 pl-9 text-xs leading-5 text-muted-foreground">{c.reason}</p>
                  )}
                  {c.scanned_at && (
                    <p className="mt-0.5 pl-9 text-[10px] text-muted-foreground/60">
                      Scanned: {new Date(c.scanned_at).toLocaleString()}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
