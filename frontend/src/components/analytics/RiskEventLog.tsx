"use client";

import React, { useState } from "react";
import { ShieldAlert } from "lucide-react";
import type { RiskEvent } from "@/types/risk";

const SEVERITY_MAP: Record<string, { label: string; class: string }> = {
  halt: { label: "Critical", class: "text-red-400 bg-red-400/10" },
  breach: { label: "Critical", class: "text-red-400 bg-red-400/10" },
  warning: { label: "Warning", class: "text-amber-400 bg-amber-400/10" },
  resume: { label: "Info", class: "text-blue-400 bg-blue-400/10" },
  info: { label: "Info", class: "text-blue-400 bg-blue-400/10" },
};

function getSeverity(eventType: string): { label: string; class: string } {
  const lower = eventType.toLowerCase();
  for (const [key, val] of Object.entries(SEVERITY_MAP)) {
    if (lower.includes(key)) return val;
  }
  return { label: "Info", class: "text-blue-400 bg-blue-400/10" };
}

type FilterLevel = "all" | "critical" | "warning" | "info";

export function RiskEventLog({ events }: { events: RiskEvent[] }) {
  const [filter, setFilter] = useState<FilterLevel>("all");

  const filtered = events.filter((e) => {
    if (filter === "all") return true;
    const sev = getSeverity(e.event_type).label.toLowerCase();
    return sev === filter;
  });

  const sorted = [...filtered].sort((a, b) => b.timestamp.localeCompare(a.timestamp));

  return (
    <div className="rounded-lg border bg-card overflow-x-auto">
      <div className="px-4 py-3 border-b flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold">
            Risk Events
            <span className="text-muted-foreground font-normal ml-2">{sorted.length}</span>
          </h3>
        </div>
        <div className="flex items-center gap-1">
          {(["all", "critical", "warning", "info"] as FilterLevel[]).map((level) => (
            <button
              key={level}
              onClick={() => setFilter(level)}
              className={`text-[10px] px-2 py-0.5 rounded font-medium transition-colors ${
                filter === level
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {level.charAt(0).toUpperCase() + level.slice(1)}
            </button>
          ))}
        </div>
      </div>
      {sorted.length === 0 ? (
        <div className="py-8 text-center text-muted-foreground text-sm">
          {filter === "all" ? "No risk events recorded" : `No ${filter} events`}
        </div>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-xs text-muted-foreground uppercase tracking-wider">
              <th className="py-2 px-4">Timestamp</th>
              <th className="py-2 px-4">Event Type</th>
              <th className="py-2 px-4">Severity</th>
              <th className="py-2 px-4">Details</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((event, i) => {
              const sev = getSeverity(event.event_type);
              return (
                <tr key={i} className="border-b border-border/50">
                  <td className="py-2 px-4 font-mono text-xs text-muted-foreground">
                    {event.timestamp.replace("T", " ").slice(0, 19)}
                  </td>
                  <td className="py-2 px-4 text-xs font-medium">{event.event_type}</td>
                  <td className="py-2 px-4">
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${sev.class}`}>
                      {sev.label}
                    </span>
                  </td>
                  <td className="py-2 px-4 text-xs text-muted-foreground max-w-xs truncate">
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
