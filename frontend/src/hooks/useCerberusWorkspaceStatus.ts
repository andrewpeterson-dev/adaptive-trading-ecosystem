"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import { listBots } from "@/lib/cerberus-api";
import type { TradingMode } from "@/hooks/useTradingMode";

type ConnectionState = "connected" | "not_connected" | "error";

interface WorkspaceConnection {
  id: number;
  provider_name: string;
  api_type: string;
  status: "connected" | "disconnected" | "error" | "pending";
  is_paper: boolean;
}

interface WorkspaceSettings {
  active_equity_broker_id: number | null;
  primary_market_data_id: number | null;
}

export interface ConnectedDataStatus {
  key: "portfolio_holdings" | "market_data" | "risk_analytics" | "bot_registry";
  label: string;
  state: ConnectionState;
  detail: string;
}

export interface CerberusWorkspaceStatus {
  connectedData: ConnectedDataStatus[];
  portfolioConnected: boolean;
  marketDataConnected: boolean;
  botRegistryConnected: boolean;
  livePermission: "enabled" | "gated" | "blocked";
  tradeProposalsEnabled: boolean;
  activeBrokerLabel: string;
  marketDataLabel: string;
  botRegistryLabel: string;
  botCount: number;
  lastUpdated: string;
}

function deriveState(
  connectedCount: number,
  errorCount: number
): ConnectionState {
  if (connectedCount > 0) return "connected";
  if (errorCount > 0) return "error";
  return "not_connected";
}

function formatConnectionDetail(
  state: ConnectionState,
  connectedLabel: string,
  missingLabel: string,
  errorLabel: string
): string {
  if (state === "connected") return connectedLabel;
  if (state === "error") return errorLabel;
  return missingLabel;
}

function buildWorkspaceStatus(
  connections: WorkspaceConnection[],
  settings: WorkspaceSettings,
  mode: TradingMode,
  botCount: number,
  botRegistryError: boolean
): CerberusWorkspaceStatus {
  const connectedBrokerage = connections.filter(
    (connection) =>
      connection.status === "connected" &&
      (connection.api_type.toUpperCase() === "BROKERAGE" ||
        connection.api_type.toUpperCase() === "CRYPTO_BROKER")
  );
  const erroredBrokerage = connections.filter(
    (connection) =>
      connection.status === "error" &&
      (connection.api_type.toUpperCase() === "BROKERAGE" ||
        connection.api_type.toUpperCase() === "CRYPTO_BROKER")
  );
  const connectedMarketData = connections.filter(
    (connection) =>
      connection.status === "connected" &&
      (connection.api_type.toUpperCase() === "MARKET_DATA" ||
        connection.api_type.toUpperCase() === "BROKERAGE" ||
        connection.api_type.toUpperCase() === "CRYPTO_BROKER")
  );
  const erroredMarketData = connections.filter(
    (connection) =>
      connection.status === "error" &&
      (connection.api_type.toUpperCase() === "MARKET_DATA" ||
        connection.api_type.toUpperCase() === "BROKERAGE" ||
        connection.api_type.toUpperCase() === "CRYPTO_BROKER")
  );

  const brokerMap = new Map(connections.map((connection) => [connection.id, connection]));
  const activeBroker = settings.active_equity_broker_id
    ? brokerMap.get(settings.active_equity_broker_id)
    : connectedBrokerage[0];
  const activeDataProvider = settings.primary_market_data_id
    ? brokerMap.get(settings.primary_market_data_id)
    : connectedMarketData[0];

  const portfolioState = deriveState(
    connectedBrokerage.length,
    erroredBrokerage.length
  );
  const marketDataState = deriveState(
    connectedMarketData.length,
    erroredMarketData.length
  );
  const riskState: ConnectionState =
    portfolioState === "connected"
      ? "connected"
      : portfolioState === "error"
        ? "error"
        : "not_connected";
  const botRegistryState: ConnectionState = botRegistryError
    ? "error"
    : "connected";

  const portfolioConnected = portfolioState === "connected";
  const marketDataConnected = marketDataState === "connected";
  const tradeProposalsEnabled = portfolioConnected && marketDataConnected;

  return {
    connectedData: [
      {
        key: "portfolio_holdings",
        label: "Portfolio holdings",
        state: portfolioState,
        detail: formatConnectionDetail(
          portfolioState,
          activeBroker
            ? `${activeBroker.provider_name} connected`
            : "Broker connected",
          "Connect a broker to inspect holdings and balances.",
          "Broker connection needs attention before holdings can be trusted."
        ),
      },
      {
        key: "market_data",
        label: "Market data",
        state: marketDataState,
        detail: formatConnectionDetail(
          marketDataState,
          activeDataProvider
            ? `${activeDataProvider.provider_name} supplying quotes`
            : "Market data available",
          "Connect a market data source for live quotes and screening.",
          "Market data provider is erroring; research and trade prompts should stay read-only."
        ),
      },
      {
        key: "risk_analytics",
        label: "Risk analytics",
        state: riskState,
        detail: formatConnectionDetail(
          riskState,
          "Risk analytics can run against current holdings.",
          "Risk analytics unlock after portfolio holdings are connected.",
          "Risk analytics are blocked because the holdings source is unhealthy."
        ),
      },
      {
        key: "bot_registry",
        label: "Bot registry",
        state: botRegistryState,
        detail: botRegistryError
          ? "Bot registry could not be loaded right now."
          : botCount > 0
            ? `${botCount} bot${botCount === 1 ? "" : "s"} available for review and deploy actions.`
            : "Registry is reachable. No bots have been deployed yet.",
      },
    ],
    portfolioConnected,
    marketDataConnected,
    botRegistryConnected: !botRegistryError,
    livePermission:
      mode === "live"
        ? portfolioConnected
          ? "enabled"
          : "blocked"
        : "gated",
    tradeProposalsEnabled,
    activeBrokerLabel: activeBroker?.provider_name ?? "Not connected",
    marketDataLabel: activeDataProvider?.provider_name ?? "Not connected",
    botRegistryLabel: botRegistryError
      ? "Unavailable"
      : botCount > 0
        ? `${botCount} registered`
        : "Ready",
    botCount,
    lastUpdated: new Date().toISOString(),
  };
}

export function useCerberusWorkspaceStatus(mode: TradingMode) {
  const [status, setStatus] = useState<CerberusWorkspaceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [connections, settings] = await Promise.all([
        apiFetch<WorkspaceConnection[]>("/api/v2/connections"),
        apiFetch<WorkspaceSettings>("/api/v2/api-settings"),
      ]);

      let botCount = 0;
      let botRegistryError = false;
      try {
        const bots = await listBots();
        botCount = bots.length;
      } catch {
        botRegistryError = true;
      }

      setStatus(
        buildWorkspaceStatus(connections, settings, mode, botCount, botRegistryError)
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load Cerberus workspace status"
      );
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    status,
    loading,
    error,
    refresh,
  };
}
