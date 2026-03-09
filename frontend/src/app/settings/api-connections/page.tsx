"use client";

import { useState, useEffect, useCallback } from "react";
import { ArrowLeft, Link2, Plus } from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { ConflictBanner } from "@/components/settings/ConflictBanner";
import {
  ApiConnectionCard,
  ApiConnection,
  ApiSettings,
} from "@/components/settings/ApiConnectionCard";
import { AvailableProviderCard } from "@/components/settings/AvailableProviderCard";
import { ConnectApiModal, ApiProvider } from "@/components/settings/ConnectApiModal";

// ─── Types ────────────────────────────────────────────────────────────────────

type ApiType =
  | "brokerage"
  | "crypto_broker"
  | "market_data"
  | "options_data"
  | "news"
  | "fundamentals"
  | "macro";

const SECTION_ORDER: ApiType[] = [
  "brokerage",
  "crypto_broker",
  "market_data",
  "options_data",
  "news",
  "fundamentals",
  "macro",
];

const SECTION_LABELS: Record<ApiType, string> = {
  brokerage: "Brokerage",
  crypto_broker: "Crypto",
  market_data: "Market Data",
  options_data: "Options Data",
  news: "News",
  fundamentals: "Fundamentals",
  macro: "Macro",
};

// ─── Loading skeleton ──────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Skeleton className="h-8 w-8 rounded-md" />
        <Skeleton className="h-6 w-48" />
      </div>
      {[...Array(3)].map((_, i) => (
        <div key={i} className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
        </div>
      ))}
    </div>
  );
}

// ─── Section component ─────────────────────────────────────────────────────────

interface SectionProps {
  apiType: ApiType;
  connections: ApiConnection[];
  providers: ApiProvider[];
  settings: ApiSettings;
  onSetActiveBroker: (id: number) => void;
  onSetActiveCrypto: (id: number) => void;
  onSetPrimaryData: (id: number) => void;
  onRemove: (id: number) => void;
  onTest: (id: number) => Promise<{ connected: boolean; error?: string }>;
  onConnectProvider: (
    provider: ApiProvider,
    credentials: Record<string, string>,
    is_paper: boolean,
    nickname?: string
  ) => Promise<void>;
}

function ApiSection({
  apiType,
  connections,
  providers,
  settings,
  onSetActiveBroker,
  onSetActiveCrypto,
  onSetPrimaryData,
  onRemove,
  onTest,
  onConnectProvider,
}: SectionProps) {
  const [addModalProvider, setAddModalProvider] = useState<ApiProvider | null>(null);

  const sectionConnections = connections.filter((c) => c.api_type === apiType);
  const sectionProviders = providers.filter((p) => p.api_type === apiType);
  // Providers not yet connected
  const connectedSlugs = new Set(sectionConnections.map((c) => c.provider_slug));
  const availableProviders = sectionProviders.filter(
    (p) => !connectedSlugs.has(p.slug)
  );

  if (sectionProviders.length === 0 && sectionConnections.length === 0) return null;

  return (
    <div className="space-y-3">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {SECTION_LABELS[apiType]}
        </h3>
        {availableProviders.length > 0 && (
          <button
            onClick={() => setAddModalProvider(availableProviders[0])}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <Plus className="h-3 w-3" />
            Add New
          </button>
        )}
      </div>

      {/* Connected cards */}
      {sectionConnections.length > 0 && (
        <div className="space-y-2">
          {sectionConnections.map((conn) => (
            <ApiConnectionCard
              key={conn.id}
              connection={conn}
              settings={settings}
              onSetActiveBroker={onSetActiveBroker}
              onSetActiveCrypto={onSetActiveCrypto}
              onSetPrimaryData={onSetPrimaryData}
              onRemove={onRemove}
              onTest={onTest}
            />
          ))}
        </div>
      )}

      {/* Available providers */}
      {availableProviders.length > 0 && (
        <div className="space-y-1.5">
          {availableProviders.map((provider) => (
            <AvailableProviderCard
              key={provider.id}
              provider={provider}
              onConnect={onConnectProvider}
            />
          ))}
        </div>
      )}

      {/* Add modal (from section-level "Add New" button) */}
      {addModalProvider && (
        <ConnectApiModal
          provider={addModalProvider}
          onConnect={async (creds, is_paper, nickname) => {
            await onConnectProvider(addModalProvider, creds, is_paper, nickname);
          }}
          onClose={() => setAddModalProvider(null)}
        />
      )}
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function ApiConnectionsPage() {
  const [providers, setProviders] = useState<ApiProvider[]>([]);
  const [connections, setConnections] = useState<ApiConnection[]>([]);
  const [settings, setSettings] = useState<ApiSettings>({
    active_equity_broker_id: null,
    active_crypto_broker_id: null,
    primary_market_data_id: null,
    fallback_market_data_ids: [],
    primary_options_data_id: null,
    conflicts: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ── Load data ────────────────────────────────────────────────────────────────

  const loadAll = useCallback(async () => {
    try {
      const [providerData, connectionData, settingsData] = await Promise.all([
        apiFetch<ApiProvider[]>("/api/v2/providers"),
        apiFetch<ApiConnection[]>("/api/v2/connections"),
        apiFetch<ApiSettings>("/api/v2/api-settings"),
      ]);
      setProviders(providerData);
      setConnections(connectionData);
      setSettings(settingsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load API connections");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // ── Actions ──────────────────────────────────────────────────────────────────

  const handleConnect = useCallback(
    async (
      provider: ApiProvider,
      credentials: Record<string, string>,
      is_paper: boolean,
      nickname?: string
    ) => {
      const newConn = await apiFetch<ApiConnection>("/api/v2/connections", {
        method: "POST",
        body: JSON.stringify({
          provider_id: provider.id,
          credentials,
          is_paper,
          nickname,
        }),
      });
      setConnections((prev) => [...prev, newConn]);
      // Refresh settings to pick up any auto-assignments
      try {
        const updated = await apiFetch<ApiSettings>("/api/v2/api-settings");
        setSettings(updated);
      } catch {
        // non-fatal
      }
    },
    []
  );

  const handleRemove = useCallback(async (id: number) => {
    await apiFetch(`/api/v2/connections/${id}`, { method: "DELETE" });
    setConnections((prev) => prev.filter((c) => c.id !== id));
    setSettings((prev) => ({
      ...prev,
      active_equity_broker_id:
        prev.active_equity_broker_id === id ? null : prev.active_equity_broker_id,
      active_crypto_broker_id:
        prev.active_crypto_broker_id === id ? null : prev.active_crypto_broker_id,
      primary_market_data_id:
        prev.primary_market_data_id === id ? null : prev.primary_market_data_id,
      fallback_market_data_ids: prev.fallback_market_data_ids.filter((fid) => fid !== id),
    }));
  }, []);

  const handleTest = useCallback(
    async (id: number): Promise<{ connected: boolean; error?: string }> => {
      return apiFetch<{ connected: boolean; error?: string }>(
        `/api/v2/connections/${id}/test`,
        { method: "POST" }
      );
    },
    []
  );

  const handleSetActiveBroker = useCallback(async (id: number) => {
    await apiFetch("/api/v2/api-settings/active-broker", {
      method: "POST",
      body: JSON.stringify({ connection_id: id }),
    });
    setSettings((prev) => ({ ...prev, active_equity_broker_id: id }));
    // Refresh conflicts
    try {
      const updated = await apiFetch<ApiSettings>("/api/v2/api-settings");
      setSettings(updated);
    } catch {
      // non-fatal
    }
  }, []);

  const handleSetActiveCrypto = useCallback(async (id: number) => {
    await apiFetch("/api/v2/api-settings/active-crypto-broker", {
      method: "POST",
      body: JSON.stringify({ connection_id: id }),
    });
    setSettings((prev) => ({ ...prev, active_crypto_broker_id: id }));
    try {
      const updated = await apiFetch<ApiSettings>("/api/v2/api-settings");
      setSettings(updated);
    } catch {
      // non-fatal
    }
  }, []);

  const handleSetPrimaryData = useCallback(
    async (id: number) => {
      const currentFallbacks = settings.fallback_market_data_ids.filter(
        (fid) => fid !== id
      );
      await apiFetch("/api/v2/api-settings/market-data-priority", {
        method: "PUT",
        body: JSON.stringify({
          primary_id: id,
          fallback_ids: currentFallbacks,
        }),
      });
      setSettings((prev) => ({
        ...prev,
        primary_market_data_id: id,
        fallback_market_data_ids: currentFallbacks,
      }));
    },
    [settings.fallback_market_data_ids]
  );

  // ── Render ───────────────────────────────────────────────────────────────────

  if (loading) return <PageSkeleton />;

  if (error) {
    return (
      <div className="rounded-xl border border-red-400/20 bg-red-400/5 px-4 py-3">
        <p className="text-sm text-red-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href="/settings"
          className="p-1.5 rounded-md border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="flex items-center gap-2">
          <Link2 className="h-5 w-5 text-primary" />
          <h2 className="text-xl font-semibold">API Connections</h2>
        </div>
      </div>

      {/* Conflict banner */}
      {settings.conflicts.length > 0 && (
        <ConflictBanner conflicts={settings.conflicts} />
      )}

      {/* Sections */}
      <div className="space-y-8">
        {SECTION_ORDER.map((apiType) => (
          <ApiSection
            key={apiType}
            apiType={apiType}
            connections={connections}
            providers={providers}
            settings={settings}
            onSetActiveBroker={handleSetActiveBroker}
            onSetActiveCrypto={handleSetActiveCrypto}
            onSetPrimaryData={handleSetPrimaryData}
            onRemove={handleRemove}
            onTest={handleTest}
            onConnectProvider={handleConnect}
          />
        ))}
      </div>
    </div>
  );
}
