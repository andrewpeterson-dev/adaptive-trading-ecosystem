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
  onSetActiveBroker: (id: number) => void;
  onSetActiveCrypto: (id: number) => void;
  onSetPrimaryData: (id: number) => void;
  onRemove: (id: number) => void;
  onTest: (id: number) => Promise<{ connected: boolean; error?: string }>;
  onEdit: (
    provider: ApiProvider,
    credentials: Record<string, string>,
    is_paper: boolean,
    nickname?: string
  ) => Promise<void>;
}

const STATUS_STYLES: Record<string, string> = {
  connected:    "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  error:        "text-red-400 bg-red-400/10 border-red-400/20",
  pending:      "text-amber-400 bg-amber-400/10 border-amber-400/20",
  disconnected: "text-muted-foreground bg-muted border-border/50",
};

const STATUS_LABELS: Record<string, string> = {
  connected:    "Connected",
  error:        "Error",
  pending:      "Pending",
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
  const [testState, setTestState]     = useState<"idle" | "loading" | "success" | "error">("idle");
  const [testError, setTestError]     = useState("");
  const [removing, setRemoving]       = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);

  // Normalise to uppercase for comparisons (backend returns uppercase)
  const apiType = connection.api_type.toUpperCase();

  const isActiveBroker = settings.active_equity_broker_id === connection.id;
  const isActiveCrypto = settings.active_crypto_broker_id === connection.id;
  const isPrimaryData  = settings.primary_market_data_id  === connection.id;
  const isFallbackData = settings.fallback_market_data_ids.includes(connection.id) && !isPrimaryData;

  const isBrokerage   = apiType === "BROKERAGE";
  const isCryptoBroker = apiType === "CRYPTO_BROKER";
  const isMarketData  = apiType === "MARKET_DATA";

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
    } finally {
      setRemoving(false);
    }
  };

  const displayName = connection.nickname ?? connection.provider_name;

  return (
    <>
      <div className="rounded-xl border border-border/50 bg-card p-4 space-y-3">
        {/* Top row */}
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1.5 min-w-0 flex-1">
            {/* Name */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold">{displayName}</span>
              {connection.nickname && (
                <span className="text-xs text-muted-foreground/70">
                  {connection.provider_name}
                </span>
              )}
            </div>

            {/* Role + mode badges */}
            <div className="flex items-center gap-1.5 flex-wrap">
              {isActiveBroker && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-widest text-blue-400 bg-blue-400/10 border-blue-400/20">
                  Active Broker
                </span>
              )}
              {isActiveCrypto && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-widest text-purple-400 bg-purple-400/10 border-purple-400/20">
                  Active Crypto
                </span>
              )}
              {isPrimaryData && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-widest text-emerald-400 bg-emerald-400/10 border-emerald-400/20">
                  Primary Data
                </span>
              )}
              {isFallbackData && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-widest text-amber-400 bg-amber-400/10 border-amber-400/20">
                  Fallback Data
                </span>
              )}
              {(isBrokerage || isCryptoBroker) && (
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-widest ${
                    connection.is_paper
                      ? "text-sky-400 bg-sky-400/10 border-sky-400/20"
                      : "text-red-400 bg-red-400/10 border-red-400/20"
                  }`}
                >
                  {connection.is_paper ? "Paper" : "Live"}
                </span>
              )}
            </div>
          </div>

          {/* Status pill */}
          <span
            className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-widest ${
              STATUS_STYLES[connection.status] ?? STATUS_STYLES.disconnected
            }`}
          >
            {STATUS_LABELS[connection.status] ?? connection.status}
          </span>
        </div>

        {/* Inline test result */}
        {testState === "success" && (
          <p className="inline-flex items-center gap-1.5 text-xs text-emerald-400">
            <CheckCircle2 className="h-3 w-3" />
            Connected
          </p>
        )}
        {testState === "error" && testError && (
          <p className="inline-flex items-center gap-1.5 text-xs text-red-400">
            <XCircle className="h-3 w-3" />
            {testError}
          </p>
        )}

        {/* Actions */}
        <div className="flex items-center gap-1.5 flex-wrap border-t border-border/40 pt-2.5">
          {/* Test */}
          <button
            onClick={handleTest}
            disabled={testState === "loading"}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border/50 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors disabled:opacity-50"
          >
            {testState === "loading" ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Plug className="h-3 w-3" />
            )}
            Test
          </button>

          {/* Edit credentials */}
          <button
            onClick={() => setShowEditModal(true)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border/50 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <Pencil className="h-3 w-3" />
            Edit
          </button>

          {/* Set as Active Broker */}
          {isBrokerage && !isActiveBroker && (
            <button
              onClick={() => onSetActiveBroker(connection.id)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-blue-400/20 text-xs text-blue-400 hover:bg-blue-400/10 transition-colors"
            >
              <Star className="h-3 w-3" />
              Set Active
            </button>
          )}

          {/* Set as Active Crypto */}
          {isCryptoBroker && !isActiveCrypto && (
            <button
              onClick={() => onSetActiveCrypto(connection.id)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-purple-400/20 text-xs text-purple-400 hover:bg-purple-400/10 transition-colors"
            >
              <Star className="h-3 w-3" />
              Set Active
            </button>
          )}

          {/* Set as Primary Data */}
          {isMarketData && !isPrimaryData && (
            <button
              onClick={() => onSetPrimaryData(connection.id)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-emerald-400/20 text-xs text-emerald-400 hover:bg-emerald-400/10 transition-colors"
            >
              <TrendingUp className="h-3 w-3" />
              Set Primary
            </button>
          )}

          {/* Remove — pushed to the right */}
          <button
            onClick={handleRemove}
            disabled={removing}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border/50 text-xs text-red-400/60 hover:text-red-400 hover:bg-red-400/5 hover:border-red-400/20 transition-colors disabled:opacity-50 ml-auto"
          >
            {removing ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="h-3 w-3" />
            )}
            Remove
          </button>
        </div>
      </div>

      {/* Edit modal */}
      {showEditModal && (
        <ConnectApiModal
          provider={provider}
          mode="edit"
          defaultNickname={connection.nickname ?? ""}
          defaultIsPaper={connection.is_paper}
          onConnect={async (creds, is_paper, nickname) => {
            await onEdit(provider, creds, is_paper, nickname);
          }}
          onClose={() => setShowEditModal(false)}
        />
      )}
    </>
  );
}
