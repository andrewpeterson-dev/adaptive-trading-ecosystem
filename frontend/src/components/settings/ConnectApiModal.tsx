"use client";

import { useState } from "react";
import { X, Eye, EyeOff, Loader2, CheckCircle2, ExternalLink } from "lucide-react";

export interface ApiProvider {
  id: number;
  slug: string;
  name: string;
  api_type:
    | "BROKERAGE"
    | "MARKET_DATA"
    | "OPTIONS_DATA"
    | "NEWS"
    | "FUNDAMENTALS"
    | "MACRO"
    | "CRYPTO_BROKER";
  supports_trading: boolean;
  supports_paper: boolean;
  supports_market_data: boolean;
  supports_options: boolean;
  supports_crypto: boolean;
  credential_fields: Array<{ key: string; label: string; secret: boolean }>;
  docs_url?: string;
}

interface ConnectApiModalProps {
  provider: ApiProvider;
  onConnect: (
    credentials: Record<string, string>,
    is_paper: boolean,
    nickname?: string
  ) => Promise<void>;
  onClose: () => void;
}

const API_TYPE_LABELS: Record<string, string> = {
  BROKERAGE: "Brokerage",
  MARKET_DATA: "Market Data",
  OPTIONS_DATA: "Options Data",
  NEWS: "News",
  FUNDAMENTALS: "Fundamentals",
  MACRO: "Macro",
  CRYPTO_BROKER: "Crypto Broker",
};

export function ConnectApiModal({
  provider,
  onConnect,
  onClose,
}: ConnectApiModalProps) {
  const [credentials, setCredentials] = useState<Record<string, string>>(
    Object.fromEntries(provider.credential_fields.map((f) => [f.key, ""]))
  );
  const [visibleFields, setVisibleFields] = useState<Record<string, boolean>>({});
  const [isPaper, setIsPaper] = useState(true);
  const [nickname, setNickname] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const showPaperToggle =
    provider.api_type === "BROKERAGE" || provider.api_type === "CRYPTO_BROKER";

  const allFilled = provider.credential_fields.every((f) => credentials[f.key]?.trim());

  const handleSubmit = async () => {
    setStatus("loading");
    setErrorMsg("");
    try {
      await onConnect(credentials, isPaper, nickname.trim() || undefined);
      setStatus("success");
      setTimeout(onClose, 1500);
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Failed to connect");
    }
  };

  const toggleVisible = (key: string) => {
    setVisibleFields((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-md rounded-xl border border-border/50 bg-card shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between p-5 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold">Connect {provider.name}</h3>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest border text-muted-foreground bg-muted border-border/50">
                {API_TYPE_LABELS[provider.api_type] ?? provider.api_type}
              </span>
            </div>
            {provider.docs_url && (
              <a
                href={provider.docs_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mt-1 transition-colors"
              >
                View docs
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 pb-5 space-y-4">
          {/* Paper/Live toggle */}
          {showPaperToggle && provider.supports_paper && (
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Mode</label>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setIsPaper(true)}
                  className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
                    isPaper
                      ? "bg-primary/10 text-primary border-primary/30"
                      : "text-muted-foreground border-border hover:bg-muted"
                  }`}
                >
                  Paper
                </button>
                <button
                  onClick={() => setIsPaper(false)}
                  className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
                    !isPaper
                      ? "bg-red-500/10 text-red-400 border-red-500/30"
                      : "text-muted-foreground border-border hover:bg-muted"
                  }`}
                >
                  Live
                </button>
              </div>
            </div>
          )}

          {/* Credential fields */}
          {provider.credential_fields.map((field) => (
            <div key={field.key} className="space-y-1.5">
              <label className="text-xs text-muted-foreground">{field.label}</label>
              <div className="relative">
                <input
                  type={field.secret && !visibleFields[field.key] ? "password" : "text"}
                  value={credentials[field.key] ?? ""}
                  onChange={(e) =>
                    setCredentials((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                  placeholder={`Enter ${field.label.toLowerCase()}...`}
                  className="w-full bg-input border border-border/50 rounded-md px-3 py-2 pr-9 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
                />
                {field.secret && (
                  <button
                    type="button"
                    onClick={() => toggleVisible(field.key)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {visibleFields[field.key] ? (
                      <EyeOff className="h-3.5 w-3.5" />
                    ) : (
                      <Eye className="h-3.5 w-3.5" />
                    )}
                  </button>
                )}
              </div>
            </div>
          ))}

          {/* Nickname */}
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">
              Nickname{" "}
              <span className="text-muted-foreground/60">(optional)</span>
            </label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              placeholder="e.g. My Alpaca Paper Account"
              className="w-full bg-input border border-border/50 rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
            />
          </div>

          {/* Feedback */}
          {status === "error" && errorMsg && (
            <p className="text-xs text-red-400">{errorMsg}</p>
          )}
          {status === "success" && (
            <p className="inline-flex items-center gap-1.5 text-xs text-emerald-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Connected successfully
            </p>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              onClick={onClose}
              className="px-3 py-1.5 rounded-md border border-border/50 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={!allFilled || status === "loading" || status === "success"}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {status === "loading" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {status === "success" && <CheckCircle2 className="h-3.5 w-3.5" />}
              {status === "loading" ? "Connecting..." : status === "success" ? "Connected" : "Connect"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
