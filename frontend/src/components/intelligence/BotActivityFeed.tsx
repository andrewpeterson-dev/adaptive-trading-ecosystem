"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Activity, ShieldAlert, Pause, Clock, TrendingUp, Search } from "lucide-react";
import { getMarketWebSocketBase } from "@/lib/websocket-url";

interface BotActivityEvent {
  event_type: string;
  bot_id: string;
  bot_name: string;
  symbol: string | null;
  headline: string;
  detail: Record<string, unknown>;
  timestamp: string;
}

const EVENT_ICONS: Record<string, typeof Activity> = {
  trade_executed: TrendingUp,
  trade_delayed: Clock,
  safety_block: ShieldAlert,
  safety_reduce: ShieldAlert,
  bot_paused: Pause,
  candidate_found: Search,
};

const EVENT_COLORS: Record<string, string> = {
  trade_executed: "text-emerald-400",
  trade_delayed: "text-amber-400",
  safety_block: "text-rose-400",
  safety_reduce: "text-amber-400",
  bot_paused: "text-rose-400",
  candidate_found: "text-blue-400",
};

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 10) return "just now";
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ago`;
}

export function BotActivityFeed() {
  const [events, setEvents] = useState<BotActivityEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const base = getMarketWebSocketBase();
    if (!base) return;

    const token = document.cookie
      .split("; ")
      .find((c) => c.startsWith("access_token="))
      ?.split("=")[1];
    if (!token) return;

    const ws = new WebSocket(`${base}/market?token=${encodeURIComponent(token)}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, 5000);
    };
    ws.onmessage = (msg) => {
      try {
        const parsed = JSON.parse(msg.data);
        if (parsed.type === "bot_activity") {
          setEvents((prev) => [parsed.data as BotActivityEvent, ...prev].slice(0, 50));
        }
      } catch {
        // ignore
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        <Activity className="h-3.5 w-3.5" />
        Bot Activity
        {connected && (
          <span className="ml-auto flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Live
          </span>
        )}
      </div>

      <div className="mt-4 max-h-[340px] space-y-2.5 overflow-y-auto scrollbar-thin">
        {events.length === 0 && (
          <p className="py-8 text-center text-xs text-muted-foreground/60">
            {connected ? "Waiting for bot activity..." : "Connecting..."}
          </p>
        )}
        {events.map((evt, i) => {
          const Icon = EVENT_ICONS[evt.event_type] ?? Activity;
          const color = EVENT_COLORS[evt.event_type] ?? "text-muted-foreground";
          return (
            <div
              key={`${evt.timestamp}-${i}`}
              className="flex items-start gap-2.5 rounded-lg border border-border/40 bg-muted/10 px-3 py-2"
            >
              <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${color}`} />
              <div className="min-w-0 flex-1">
                <p className="text-xs leading-snug text-foreground/90">{evt.headline}</p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  {evt.bot_name}
                  {evt.symbol ? ` / ${evt.symbol}` : ""}
                  {" \u00B7 "}
                  {timeAgo(evt.timestamp)}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
