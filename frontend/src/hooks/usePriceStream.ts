"use client";

import { useState, useEffect, useRef, useCallback } from "react";

export interface PriceData {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  volume: number;
  change: number;
  change_pct: number;
  timestamp: number;
  source?: string;
}

interface UsePriceStreamResult {
  prices: Record<string, PriceData>;
  connected: boolean;
  subscribe: (symbols: string[]) => void;
  unsubscribe: (symbols: string[]) => void;
}

function getAuthToken(): string {
  if (typeof window === "undefined") return "";
  const match = document.cookie.match(/(?:^|; )auth_token=([^;]*)/);
  if (match) return decodeURIComponent(match[1]);
  return localStorage.getItem("auth_token") ?? "";
}

function getWsBase(): string {
  if (typeof window === "undefined") return "";
  // Use NEXT_PUBLIC_WS_URL if set, otherwise derive from current host
  // In local dev: ws://localhost:8000/ws
  // In Docker/prod: set NEXT_PUBLIC_WS_URL=ws://your-api-host/ws
  const envUrl = process.env.NEXT_PUBLIC_WS_URL;
  if (envUrl) return envUrl;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.hostname;
  return `${proto}://${host}:8000/ws`;
}

export function usePriceStream(initialSymbols: string[] = []): UsePriceStreamResult {
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const subscribedRef = useRef<Set<string>>(new Set(initialSymbols.map((s) => s.toUpperCase())));
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  const sendMsg = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const subscribe = useCallback((symbols: string[]) => {
    const upper = symbols.map((s) => s.toUpperCase());
    upper.forEach((s) => subscribedRef.current.add(s));
    sendMsg({ subscribe: upper });
  }, [sendMsg]);

  const unsubscribe = useCallback((symbols: string[]) => {
    const upper = symbols.map((s) => s.toUpperCase());
    upper.forEach((s) => subscribedRef.current.delete(s));
    sendMsg({ unsubscribe: upper });
  }, [sendMsg]);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;
    const token = getAuthToken();
    if (!token) return;

    const url = `${getWsBase()}/market?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      // Subscribe to all tracked symbols on (re)connect
      if (subscribedRef.current.size > 0) {
        ws.send(JSON.stringify({ subscribe: Array.from(subscribedRef.current) }));
      }
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "price_update" && msg.data?.symbol) {
          setPrices((prev) => ({ ...prev, [msg.data.symbol]: msg.data }));
        }
      } catch {
        // ignore
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      if (!unmountedRef.current) {
        reconnectTimer.current = setTimeout(connect, 3000);
      }
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    unmountedRef.current = false;
    connect();
    return () => {
      unmountedRef.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { prices, connected, subscribe, unsubscribe };
}
