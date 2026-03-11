"use client";

import React, { useState } from "react";
import { ShieldAlert } from "lucide-react";
import type { RiskEvent } from "@/types/risk";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

const SEVERITY_MAP: Record<string, { label: string; class: string }> = {
  halt: { label: "Critical", class: "text-red-300 bg-red-400/10 border-red-400/20" },
  breach: { label: "Critical", class: "text-red-300 bg-red-400/10 border-red-400/20" },
  warning: { label: "Warning", class: "text-amber-300 bg-amber-400/10 border-amber-400/20" },
  resume: { label: "Info", class: "text-sky-300 bg-sky-400/10 border-sky-400/20" },
  info: { label: "Info", class: "text-sky-300 bg-sky-400/10 border-sky-400/20" },
};

function getSeverity(eventType: string): { label: string; class: string } {
  const lower = eventType.toLowerCase();
  for (const [key, val] of Object.entries(SEVERITY_MAP)) {
    if (lower.includes(key)) return val;
  }
  return { label: "Info", class: "text-sky-300 bg-sky-400/10 border-sky-400/20" };
}

type FilterLevel = "all" | "critical" | "warning" | "info";

export function RiskEventLog({ events }: { events: RiskEvent[] }) {
  const [filter, setFilter] = useState<FilterLevel>("all");

  const filtered = events.filter((event) => {
    if (filter === "all") return true;
    return getSeverity(event.event_type).label.toLowerCase() === filter;
  });

  const sorted = [...filtered].sort((a, b) => b.timestamp.localeCompare(a.timestamp));

  return (
    <div className="app-table-shell overflow-x-auto">
      <div className="app-section-header">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">
            Risk Events
            <span className="ml-2 font-normal text-muted-foreground">{sorted.length}</span>
          </h3>
        </div>
        <div className="flex items-center gap-1">
          {(["all", "critical", "warning", "info"] as FilterLevel[]).map((level) => (
            <Button
              key={level}
              onClick={() => setFilter(level)}
              variant={filter === level ? "secondary" : "ghost"}
              size="sm"
              className="h-8 rounded-full px-3 text-[10px] uppercase tracking-[0.16em]"
            >
              {level}
            </Button>
          ))}
        </div>
      </div>
      {sorted.length === 0 ? (
        <EmptyState
          title={filter === "all" ? "No risk events recorded" : `No ${filter} events`}
          description="Halts, resumptions, and policy breaches will appear here once live risk workflows are producing events."
          className="py-12"
        />
      ) : (
        <table className="app-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Event Type</th>
              <th>Severity</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((event, index) => {
              const severity = getSeverity(event.event_type);
              return (
                <tr key={index}>
                  <td className="font-mono text-xs tabular-nums text-muted-foreground">
                    {event.timestamp.replace("T", " ").slice(0, 19)}
                  </td>
                  <td className="text-xs font-medium">{event.event_type}</td>
                  <td>
                    <span
                      className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${severity.class}`}
                    >
                      {severity.label}
                    </span>
                  </td>
                  <td className="max-w-xs text-xs text-muted-foreground">
                    {event.description}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
