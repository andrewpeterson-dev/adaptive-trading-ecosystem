"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api/client";
import type { OptionsNotSupportedPayload } from "@/hooks/useOptionsGuard";
import type { ApiConnection, ApiProvider } from "./ApiConnectionCard";
import { ConnectApiModal } from "./ConnectApiModal";

interface Props {
  payload: OptionsNotSupportedPayload;
  connections: ApiConnection[];
  providers: ApiProvider[];
  onEnabled: () => void;
  onDismiss: () => void;
}

export function OptionsFallbackModal({ payload, connections, providers, onEnabled, onDismiss }: Props) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<number | null>(null);
  const [connectingProvider, setConnectingProvider] = useState<ApiProvider | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const optionsConnections = connections.filter((c) => {
    const prov = providers.find((p) => p.id === c.provider_id);
    return (prov as any)?.supports_options && (prov as any)?.supports_paper;
  });

  const connectableProviders = providers.filter((p) => {
    const connected = connections.some((c) => c.provider_id === p.id);
    return (p as any).supports_options && (p as any).supports_paper && !connected;
  });

  const handleEnable = async () => {
    if (!selectedConnectionId) return;
    setLoading(true);
    setError("");
    try {
      await apiFetch("/api/v2/api-settings/options-fallback", {
        method: "POST",
        body: JSON.stringify({ enabled: true, provider_connection_id: selectedConnectionId }),
      });
      onEnabled();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to enable options fallback");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl space-y-5">
        <div>
          <h2 className="text-base font-semibold">Options Not Supported</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{payload.active_broker}</span> doesn't
            support options trading via API. You can simulate options using a separate provider.
          </p>
        </div>

        <div className="rounded-xl border border-border bg-muted/30 p-4 space-y-2 text-sm">
          <p className="font-medium text-xs uppercase tracking-widest text-muted-foreground">Impact</p>
          <ul className="space-y-1">
            <li className="flex gap-2">
              <span className="text-amber-400">↪</span>
              <span>Options orders will be routed to your chosen options provider (paper)</span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400">✓</span>
              <span>Your {payload.active_broker} equity, cash, and stock positions are <strong>unaffected</strong></span>
            </li>
            <li className="flex gap-2">
              <span className="text-emerald-400">✓</span>
              <span>P&L shown separately: <em>Broker Equity</em> + <em>Options Sim P&L</em> = Total</span>
            </li>
          </ul>
        </div>

        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Route options to</p>
          {optionsConnections.length > 0 ? (
            <div className="space-y-1.5">
              {optionsConnections.map((conn) => {
                const prov = providers.find((p) => p.id === conn.provider_id);
                return (
                  <button
                    key={conn.id}
                    onClick={() => setSelectedConnectionId(conn.id)}
                    className={`w-full flex items-center justify-between rounded-xl border px-4 py-2.5 text-sm transition-colors ${
                      selectedConnectionId === conn.id
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border hover:border-primary/40"
                    }`}
                  >
                    <span>{prov?.name ?? conn.nickname ?? "Unknown"}</span>
                    <span className="text-xs text-muted-foreground">{conn.is_paper ? "Paper" : "Live"}</span>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No options-capable providers connected.{" "}
              {connectableProviders.length > 0 && (
                <button className="text-primary underline" onClick={() => setConnectingProvider(connectableProviders[0])}>
                  Connect {connectableProviders[0].name}
                </button>
              )}
            </p>
          )}
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="flex gap-3">
          <button onClick={onDismiss} className="flex-1 rounded-xl border border-border px-4 py-2 text-sm hover:bg-muted/50">
            Cancel
          </button>
          <button
            onClick={handleEnable}
            disabled={!selectedConnectionId || loading}
            className="flex-1 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-40"
          >
            {loading ? "Enabling…" : "Enable Options Fallback"}
          </button>
        </div>
      </div>

      {connectingProvider && (
        <ConnectApiModal
          provider={connectingProvider}
          onConnect={async () => { setConnectingProvider(null); }}
          onClose={() => setConnectingProvider(null)}
        />
      )}
    </div>
  );
}
