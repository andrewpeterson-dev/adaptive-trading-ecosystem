"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { ApiError } from "@/lib/api/client";
import { getWebSocketToken } from "@/lib/api/auth";
import { getMarketWebSocketBase } from "@/lib/websocket-url";

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

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 30_000;

export function usePriceStream(initialSymbols: string[] = []): UsePriceStreamResult {
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const subscribedRef = useRef<Set<string>>(new Set(initialSymbols.map((s) => s.toUpperCase())));
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttempts = useRef(0);
  const unmountedRef = useRef(false);

  // Batch WS price updates: accumulate in ref, flush once per animation frame
  const pendingUpdates = useRef<Record<string, PriceData>>({});
  const rafId = useRef<number | null>(null);

  const flushUpdates = useCallback(() => {
    rafId.current = null;
    const batch = pendingUpdates.current;
    if (Object.keys(batch).length === 0) return;
    pendingUpdates.current = {};
    setPrices((prev) => ({ ...prev, ...batch }));
  }, []);

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

  const connect = useCallback(async () => {
    if (unmountedRef.current) return;
    try {
      const { token } = await getWebSocketToken();
      const url = `${getMarketWebSocketBase()}/market?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        reconnectAttempts.current = 0;
        if (subscribedRef.current.size > 0) {
          ws.send(JSON.stringify({ subscribe: Array.from(subscribedRef.current) }));
        }
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === "price_update" && msg.data?.symbol) {
            pendingUpdates.current[msg.data.symbol] = msg.data;
            if (rafId.current === null) {
              rafId.current = requestAnimationFrame(flushUpdates);
            }
          }
        } catch {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (!unmountedRef.current && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            BASE_RECONNECT_DELAY_MS * 2 ** reconnectAttempts.current,
            MAX_RECONNECT_DELAY_MS
          );
          reconnectAttempts.current++;
          reconnectTimer.current = setTimeout(() => {
            void connect();
          }, delay);
        }
      };

      ws.onerror = () => ws.close();
    } catch (error) {
      setConnected(false);
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        return;
      }
      if (!unmountedRef.current && reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = Math.min(
          BASE_RECONNECT_DELAY_MS * 2 ** reconnectAttempts.current,
          MAX_RECONNECT_DELAY_MS
        );
        reconnectAttempts.current++;
        reconnectTimer.current = setTimeout(() => {
          void connect();
        }, delay);
      }
    }
  }, [flushUpdates]);

  useEffect(() => {
    unmountedRef.current = false;
    void connect();
    return () => {
      unmountedRef.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (rafId.current !== null) cancelAnimationFrame(rafId.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { prices, connected, subscribe, unsubscribe };
}
