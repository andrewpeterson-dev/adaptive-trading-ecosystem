"use client";

import { useState } from "react";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Trash2,
  Plug,
  Star,
  TrendingUp,
  Pencil,
} from "lucide-react";
import { ConnectApiModal, ApiProvider } from "./ConnectApiModal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export interface ApiConnection {
  id: number;
  provider_id: number;
  provider_name: string;
  provider_slug: string;
  api_type: string;
  status: "connected" | "disconnected" | "error" | "pending";
  is_paper: boolean;
  nickname?: string;
  created_at: string;
  last_tested_at?: string;
}

export interface ApiSettings {
  active_equity_broker_id: number | null;
  active_crypto_broker_id: number | null;
  primary_market_data_id: number | null;
  fallback_market_data_ids: number[];
  primary_options_data_id: number | null;
  conflicts: Array<{ type: string; message: string; affected_ids: number[] }>;
}

interface ApiConnectionCardProps {
  connection: ApiConnection;
  provider: ApiProvider;
  settings: ApiSettings;
  onSetActiveBroker: (id: number) => Promise<void>;
  onSetActiveCrypto: (id: number) => Promise<void>;
  onSetPrimaryData: (id: number) => Promise<void>;
  onRemove: (id: number) => Promise<void>;
  onTest: (id: number) => Promise<{ connected: boolean; error?: string }>;
  onEdit: (
    provider: ApiProvider,
    credentials: Record<string, string>,
    is_paper: boolean,
    nickname?: string
  ) => Promise<void>;
}

const STATUS_VARIANTS: Record<string, "neutral" | "success" | "danger" | "warning"> = {
  connected: "success",
  error: "danger",
  pending: "warning",
  disconnected: "neutral",
};

const STATUS_LABELS: Record<string, string> = {
  connected: "Connected",
  error: "Error",
  pending: "Pending",
  disconnected: "Disconnected",
};

export function ApiConnectionCard({
  connection,
  provider,
  settings,
  onSetActiveBroker,
  onSetActiveCrypto,
  onSetPrimaryData,
  onRemove,
  onTest,
  onEdit,
}: ApiConnectionCardProps) {
  const [testState, setTestState] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [testError, setTestError] = useState("");
  const [removing, setRemoving] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const apiType = connection.api_type.toUpperCase();
  const isActiveBroker = settings.active_equity_broker_id === connection.id;
  const isActiveCrypto = settings.active_crypto_broker_id === connection.id;
  const isPrimaryData = settings.primary_market_data_id === connection.id;
  const isFallbackData =
    settings.fallback_market_data_ids.includes(connection.id) && !isPrimaryData;

  const isBrokerage = apiType === "BROKERAGE";
  const isCryptoBroker = apiType === "CRYPTO_BROKER";
  const isMarketData = apiType === "MARKET_DATA";

  const handleTest = async () => {
    setTestState("loading");
    setTestError("");
    try {
      const result = await onTest(connection.id);
      if (result.connected) {
        setTestState("success");
        setTimeout(() => setTestState("idle"), 4000);
      } else {
        setTestState("error");
        setTestError(result.error ?? "Connection failed");
      }
    } catch {
      setTestState("error");
      setTestError("Test request failed");
    }
  };

  const handleRemove = async () => {
    setRemoving(true);
    try {
      await onRemove(connection.id);
    } catch {
      // parent callback surfaces the failure
    } finally {
      setRemoving(false);
    }
  };

  const handleSetActiveBroker = async () => {
    setActionError(null);
    try {
      await onSetActiveBroker(connection.id);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to set active broker");
    }
  };

  const handleSetActiveCrypto = async () => {
    setActionError(null);
    try {
      await onSetActiveCrypto(connection.id);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to set active crypto");
    }
  };

  const handleSetPrimaryData = async () => {
    setActionError(null);
    try {
      await onSetPrimaryData(connection.id);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Failed to set primary data source");
    }
  };

  const displayName = connection.nickname ?? connection.provider_name;

  return (
    <>
      <div className="app-card space-y-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-foreground">{displayName}</span>
              {connection.nickname && (
                <span className="text-xs text-muted-foreground">{connection.provider_name}</span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={STATUS_VARIANTS[connection.status] ?? "neutral"}>
                {STATUS_LABELS[connection.status] ?? connection.status}
              </Badge>
              {isActiveBroker && <Badge variant="primary">Active Broker</Badge>}
              {isActiveCrypto && <Badge variant="info">Active Crypto</Badge>}
              {isPrimaryData && <Badge variant="success">Primary Data</Badge>}
              {isFallbackData && <Badge variant="warning">Fallback Data</Badge>}
              {(isBrokerage || isCryptoBroker) && (
                <Badge variant={connection.is_paper ? "info" : "danger"}>
                  {connection.is_paper ? "Paper" : "Live"}
                </Badge>
              )}
            </div>
          </div>
        </div>

        {testState === "success" && (
          <p className="inline-flex items-center gap-1.5 text-xs text-emerald-300">
            <CheckCircle2 className="h-3 w-3" />
            Connection healthy
          </p>
        )}
        {testState === "error" && testError && (
          <p className="inline-flex items-center gap-1.5 text-xs text-red-300">
            <XCircle className="h-3 w-3" />
            {testError}
          </p>
        )}
        {actionError && (
          <p className="inline-flex items-center gap-1.5 text-xs text-red-300">
            <XCircle className="h-3 w-3" />
            {actionError}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-3">
          <Button
            onClick={handleTest}
            disabled={testState === "loading"}
            variant="secondary"
            size="sm"
            className="h-9 rounded-full px-3"
          >
            {testState === "loading" ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Plug className="h-3 w-3" />
            )}
            Test
          </Button>

          <Button
            onClick={() => setShowEditModal(true)}
            variant="secondary"
            size="sm"
            className="h-9 rounded-full px-3"
          >
            <Pencil className="h-3 w-3" />
            Edit
          </Button>

          {isBrokerage && !isActiveBroker && (
            <Button
              onClick={() => void handleSetActiveBroker()}
              variant="secondary"
              size="sm"
              className="h-9 rounded-full px-3"
            >
              <Star className="h-3 w-3" />
              Set Active
            </Button>
          )}

          {isCryptoBroker && !isActiveCrypto && (
            <Button
              onClick={() => void handleSetActiveCrypto()}
              variant="secondary"
              size="sm"
              className="h-9 rounded-full px-3"
            >
              <Star className="h-3 w-3" />
              Set Active
            </Button>
          )}

          {isMarketData && !isPrimaryData && (
            <Button
              onClick={() => void handleSetPrimaryData()}
              variant="secondary"
              size="sm"
              className="h-9 rounded-full px-3"
            >
              <TrendingUp className="h-3 w-3" />
              Set Primary
            </Button>
          )}

          <Button
            onClick={handleRemove}
            disabled={removing}
            variant="danger"
            size="sm"
            className="ml-auto h-9 rounded-full px-3"
          >
            {removing ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="h-3 w-3" />
            )}
            Remove
          </Button>
        </div>
      </div>

      {showEditModal && (
        <ConnectApiModal
          provider={provider}
          mode="edit"
          defaultNickname={connection.nickname ?? ""}
          defaultIsPaper={connection.is_paper}
          onClose={() => setShowEditModal(false)}
          onConnect={async (credentials, isPaper, nickname) => {
            await onEdit(provider, credentials, isPaper, nickname);
            setShowEditModal(false);
          }}
        />
      )}
    </>
  );
}
