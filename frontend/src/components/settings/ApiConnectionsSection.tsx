"use client";

import { useState, useEffect, useCallback } from "react";
import { Plus } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ConflictBanner } from "@/components/settings/ConflictBanner";
import {
  ApiConnectionCard,
  ApiConnection,
  ApiSettings,
} from "@/components/settings/ApiConnectionCard";
import { AvailableProviderCard } from "@/components/settings/AvailableProviderCard";
import { ConnectApiModal, ApiProvider } from "@/components/settings/ConnectApiModal";

// ─── Types ────────────────────────────────────────────────────────────────────

// Must match backend ApiProviderType enum (uppercase)
type ApiType =
  | "BROKERAGE"
  | "CRYPTO_BROKER"
  | "MARKET_DATA"
  | "OPTIONS_DATA"
  | "NEWS"
  | "FUNDAMENTALS"
  | "MACRO";

const SECTION_ORDER: ApiType[] = [
  "BROKERAGE",
  "CRYPTO_BROKER",
  "MARKET_DATA",
  "OPTIONS_DATA",
  "NEWS",
  "FUNDAMENTALS",
  "MACRO",
];

const SECTION_LABELS: Record<ApiType, string> = {
  BROKERAGE: "Brokerage",
  CRYPTO_BROKER: "Crypto",
  MARKET_DATA: "Market Data",
  OPTIONS_DATA: "Options Data",
  NEWS: "News",
  FUNDAMENTALS: "Fundamentals",
  MACRO: "Macro",
};

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function SectionSkeleton() {
  return (
    <div className="space-y-6">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="space-y-3">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-20 w-full rounded-xl" />
          <Skeleton className="h-10 w-full rounded-xl" />
        </div>
      ))}
    </div>
  );
}

// ─── Per-type section ─────────────────────────────────────────────────────────

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
  providerMap: Map<number, ApiProvider>;
}

function ApiTypeSection({
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
  providerMap,
}: SectionProps) {
  const [addModalProvider, setAddModalProvider] = useState<ApiProvider | null>(null);

  const sectionConnections = connections.filter(
    (c) => c.api_type.toUpperCase() === apiType
  );
  const sectionProviders = providers.filter(
    (p) => p.api_type.toUpperCase() === apiType
  );
  const connectedSlugs = new Set(sectionConnections.map((c) => c.provider_slug));
  const availableProviders = sectionProviders.filter((p) => !connectedSlugs.has(p.slug));

  if (sectionProviders.length === 0 && sectionConnections.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-0.5">
        <span className="app-label">
          {SECTION_LABELS[apiType]}
        </span>
        {availableProviders.length > 0 && (
          <Button
            onClick={() => setAddModalProvider(availableProviders[0])}
            variant="ghost"
            size="sm"
            className="h-8 px-2 text-[10px] uppercase tracking-[0.16em]"
          >
            <Plus className="h-3 w-3" />
            Add
          </Button>
        )}
      </div>
      {sectionConnections.map((conn) => {
        const provider = providerMap.get(conn.provider_id);
        if (!provider) return null;
        return (
          <ApiConnectionCard
            key={conn.id}
            connection={conn}
            provider={provider}
            settings={settings}
            onSetActiveBroker={onSetActiveBroker}
            onSetActiveCrypto={onSetActiveCrypto}
            onSetPrimaryData={onSetPrimaryData}
            onRemove={onRemove}
            onTest={onTest}
            onEdit={onConnectProvider}
          />
        );
      })}
      {availableProviders.map((provider) => (
        <AvailableProviderCard
          key={provider.id}
          provider={provider}
          onConnect={onConnectProvider}
        />
      ))}
      {addModalProvider && (
        <ConnectApiModal
          provider={addModalProvider}
          onConnect={async (creds, is_paper, nickname) => {
            await onConnectProvider(addModalProvider, creds, is_paper, nickname);
            setAddModalProvider(null);
          }}
          onClose={() => setAddModalProvider(null)}
        />
      )}
    </div>
  );
}

// ─── Main exported component ──────────────────────────────────────────────────

export function ApiConnectionsSection() {
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

  const loadAll = useCallback(async () => {
    try {
      const [providerData, connectionData, settingsData] = await Promise.all([
        apiFetch<ApiProvider[]>("/api/v2/providers"),
        apiFetch<ApiConnection[]>("/api/v2/connections"),
        apiFetch<ApiSettings>("/api/v2/api-settings"),
      ]);
      // Normalize api_type to UPPERCASE at the fetch boundary so all downstream
      // components can safely use uppercase comparisons (e.g. "BROKERAGE").
      const normalize = <T extends { api_type: string }>(items: T[]): T[] =>
        items.map((item) => ({ ...item, api_type: item.api_type.toUpperCase() }));
      setProviders(normalize(providerData) as ApiProvider[]);
      setConnections(normalize(connectionData) as ApiConnection[]);
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

  const refreshSettings = useCallback(async () => {
    try {
      const updated = await apiFetch<ApiSettings>("/api/v2/api-settings");
      setSettings(updated);
    } catch {
      // non-fatal
    }
  }, []);

  const handleConnect = useCallback(
    async (
      provider: ApiProvider,
      credentials: Record<string, string>,
      is_paper: boolean,
      nickname?: string
    ) => {
      const newConn = await apiFetch<ApiConnection>("/api/v2/connections", {
        method: "POST",
        body: JSON.stringify({ provider_id: provider.id, credentials, is_paper, nickname }),
      });
      setConnections((prev) => {
        const idx = prev.findIndex((c) => c.provider_id === newConn.provider_id);
        return idx >= 0
          ? prev.map((c, i) => (i === idx ? newConn : c))
          : [...prev, newConn];
      });
      await refreshSettings();
    },
    [refreshSettings]
  );

  const handleRemove = useCallback(
    async (id: number) => {
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
    },
    []
  );

  const handleTest = useCallback(
    async (id: number): Promise<{ connected: boolean; error?: string }> =>
      apiFetch<{ connected: boolean; error?: string }>(
        `/api/v2/connections/${id}/test`,
        { method: "POST" }
      ),
    []
  );

  const handleSetActiveBroker = useCallback(
    async (id: number) => {
      await apiFetch("/api/v2/api-settings/active-broker", {
        method: "POST",
        body: JSON.stringify({ connection_id: id }),
      });
      await refreshSettings();
    },
    [refreshSettings]
  );

  const handleSetActiveCrypto = useCallback(
    async (id: number) => {
      await apiFetch("/api/v2/api-settings/active-crypto-broker", {
        method: "POST",
        body: JSON.stringify({ connection_id: id }),
      });
      await refreshSettings();
    },
    [refreshSettings]
  );

  const handleSetPrimaryData = useCallback(
    async (id: number) => {
      const fallbacks = settings.fallback_market_data_ids.filter((fid) => fid !== id);
      await apiFetch("/api/v2/api-settings/market-data-priority", {
        method: "PUT",
        body: JSON.stringify({ primary_id: id, fallback_ids: fallbacks }),
      });
      await refreshSettings();
    },
    [settings.fallback_market_data_ids, refreshSettings]
  );

  if (loading) return <SectionSkeleton />;

  if (error) {
    return (
      <EmptyState title="API connections unavailable" description={error} />
    );
  }

  // Build provider lookup map once per render
  const providerMap = new Map(providers.map((p) => [p.id, p]));

  return (
    <div className="space-y-6">
      {settings.conflicts.length > 0 && (
        <ConflictBanner conflicts={settings.conflicts} />
      )}

      {SECTION_ORDER.map((apiType) => (
        <ApiTypeSection
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
          providerMap={providerMap}
        />
      ))}
    </div>
  );
}
