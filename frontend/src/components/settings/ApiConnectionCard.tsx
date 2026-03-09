"use client";

import { useState } from "react";
import { Loader2, CheckCircle2, XCircle, Trash2, Plug, Star, TrendingUp } from "lucide-react";

export interface ApiConnection {
  id: number;
  provider_id: number;
  provider_name: string;
  provider_slug: string;
  api_type: string;
  status: "connected" | "disconnected" | "error" | "pending";
  is_paper: boolean;
  unified_mode?: boolean;
  supports_market_data?: boolean;
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
  settings: ApiSettings;
  onSetActiveBroker: (id: number) => void;
  onSetActiveCrypto: (id: number) => void;
  onSetPrimaryData: (id: number) => void;
  onRemove: (id: number) => void;
  onTest: (id: number) => Promise<{ connected: boolean; error?: string }>;
}

const STATUS_STYLES: Record<string, string> = {
  connected: "text-emerald-400 bg-emerald-400/10",
  error: "text-red-400 bg-red-400/10",
  pending: "text-amber-400 bg-amber-400/10",
  disconnected: "text-muted-foreground bg-muted",
};

const STATUS_LABELS: Record<string, string> = {
  connected: "Connected",
  error: "Error",
  pending: "Pending",
  disconnected: "Disconnected",
};

export function ApiConnectionCard({
  connection,
  settings,
  onSetActiveBroker,
  onSetActiveCrypto,
  onSetPrimaryData,
  onRemove,
  onTest,
}: ApiConnectionCardProps) {
  const [testState, setTestState] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [testError, setTestError] = useState("");
  const [removing, setRemoving] = useState(false);

  const isActiveBroker = settings.active_equity_broker_id === connection.id;
  const isActiveCrypto = settings.active_crypto_broker_id === connection.id;
  const isPrimaryData = settings.primary_market_data_id === connection.id;
  const isFallbackData = settings.fallback_market_data_ids.includes(connection.id);

  const isBrokerage = connection.api_type === "brokerage";
  const isCryptoBroker = connection.api_type === "crypto_broker";
  const isMarketData = connection.api_type === "market_data";

  const handleTest = async () => {
    setTestState("loading");
    setTestError("");
    try {
      const result = await onTest(connection.id);
      if (result.connected) {
        setTestState("success");
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
    <div className="rounded-xl border border-border/50 bg-card p-4 space-y-3">
      {/* Top row: name + status + paper badge */}
      <div className="flex items-start justify-between gap-2">
        <div className="space-y-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold truncate">{displayName}</span>
            {connection.nickname && (
              <span className="text-xs text-muted-foreground">
                ({connection.provider_name})
              </span>
            )}
          </div>

          {/* Role badges */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {isActiveBroker && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest border text-blue-400 bg-blue-400/10 border-blue-400/20">
                Active Broker
              </span>
            )}
            {isActiveCrypto && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest border text-purple-400 bg-purple-400/10 border-purple-400/20">
                Active Crypto
              </span>
            )}
            {isPrimaryData && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest border text-emerald-400 bg-emerald-400/10 border-emerald-400/20">
                Primary Data
              </span>
            )}
            {isFallbackData && !isPrimaryData && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest border text-amber-400 bg-amber-400/10 border-amber-400/20">
                Fallback Data
              </span>
            )}
            {(isBrokerage || isCryptoBroker) && connection.unified_mode ? (
              // Unified key covers everything — show capability tags
              <>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest border text-sky-400 bg-sky-400/10 border-sky-400/20">
                  Paper + Live
                </span>
                {connection.supports_market_data && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest border text-violet-400 bg-violet-400/10 border-violet-400/20">
                    Quotes
                  </span>
                )}
              </>
            ) : (isBrokerage || isCryptoBroker) ? (
              // Mode-specific credential — show which mode this key is for
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest border ${
                  connection.is_paper
                    ? "text-primary bg-primary/10 border-primary/20"
                    : "text-red-400 bg-red-400/10 border-red-400/20"
                }`}
              >
                {connection.is_paper ? "Paper" : "Live"}
              </span>
            ) : null}
          </div>
        </div>

        {/* Status pill */}
        <span
          className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest ${
            STATUS_STYLES[connection.status] ?? STATUS_STYLES.disconnected
          }`}
        >
          {STATUS_LABELS[connection.status] ?? connection.status}
        </span>
      </div>

      {/* Test result */}
      {testState === "success" && (
        <p className="inline-flex items-center gap-1 text-xs text-emerald-400">
          <CheckCircle2 className="h-3 w-3" />
          Connected
        </p>
      )}
      {testState === "error" && testError && (
        <p className="inline-flex items-center gap-1 text-xs text-red-400">
          <XCircle className="h-3 w-3" />
          {testError}
        </p>
      )}

      {/* Actions row */}
      <div className="flex items-center gap-2 flex-wrap pt-0.5">
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

        {/* Set as Active Broker */}
        {isBrokerage && !isActiveBroker && (
          <button
            onClick={() => onSetActiveBroker(connection.id)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-blue-400/20 text-xs text-blue-400 hover:bg-blue-400/10 transition-colors"
          >
            <Star className="h-3 w-3" />
            Set as Active
          </button>
        )}

        {/* Set as Active Crypto */}
        {isCryptoBroker && !isActiveCrypto && (
          <button
            onClick={() => onSetActiveCrypto(connection.id)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-purple-400/20 text-xs text-purple-400 hover:bg-purple-400/10 transition-colors"
          >
            <Star className="h-3 w-3" />
            Set as Active
          </button>
        )}

        {/* Set as Primary Data */}
        {isMarketData && !isPrimaryData && (
          <button
            onClick={() => onSetPrimaryData(connection.id)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-emerald-400/20 text-xs text-emerald-400 hover:bg-emerald-400/10 transition-colors"
          >
            <TrendingUp className="h-3 w-3" />
            Set as Primary
          </button>
        )}

        {/* Remove */}
        <button
          onClick={handleRemove}
          disabled={removing}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border/50 text-xs text-red-400/70 hover:text-red-400 hover:bg-red-400/5 hover:border-red-400/20 transition-colors disabled:opacity-50 ml-auto"
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
  );
}
