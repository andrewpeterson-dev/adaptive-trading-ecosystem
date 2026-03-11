"use client";

import { useState } from "react";
import {
  Eye,
  EyeOff,
  Loader2,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
  unified_mode?: boolean;
  credential_note?: string;
  credential_fields: Array<{ key: string; label: string; secret: boolean }>;
  docs_url?: string;
}

interface ConnectApiModalProps {
  provider: ApiProvider;
  mode?: "connect" | "edit";
  defaultNickname?: string;
  defaultIsPaper?: boolean;
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
  mode = "connect",
  defaultNickname = "",
  defaultIsPaper = true,
  onConnect,
  onClose,
}: ConnectApiModalProps) {
  const [credentials, setCredentials] = useState<Record<string, string>>(
    Object.fromEntries(provider.credential_fields.map((field) => [field.key, ""]))
  );
  const [visibleFields, setVisibleFields] = useState<Record<string, boolean>>({});
  const [isPaper, setIsPaper] = useState(defaultIsPaper);
  const [nickname, setNickname] = useState(defaultNickname);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const isEdit = mode === "edit";
  const showPaperToggle =
    !provider.unified_mode &&
    provider.supports_paper &&
    (provider.api_type === "BROKERAGE" || provider.api_type === "CRYPTO_BROKER");

  const allFilled = isEdit
    ? true
    : provider.credential_fields.every((field) => credentials[field.key]?.trim());

  const handleSubmit = async () => {
    const payload = isEdit
      ? Object.fromEntries(
          Object.entries(credentials).filter(([, value]) => value.trim() !== "")
        )
      : credentials;

    if (!isEdit && !allFilled) return;

    setStatus("loading");
    setErrorMsg("");
    try {
      await onConnect(payload, isPaper, nickname.trim() || undefined);
      setStatus("success");
      setTimeout(onClose, 1200);
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Failed to save");
    }
  };

  const toggleVisible = (key: string) => {
    setVisibleFields((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg overflow-hidden">
        <DialogHeader className="border-b border-border/60 pb-4">
          <div className="flex flex-wrap items-center gap-2">
            <DialogTitle>{isEdit ? "Update" : "Connect"} {provider.name}</DialogTitle>
            <Badge variant="neutral">
              {API_TYPE_LABELS[provider.api_type] ?? provider.api_type}
            </Badge>
          </div>
          <DialogDescription>
            {isEdit
              ? "Leave any credential blank to preserve the stored value."
              : "Store encrypted credentials and bind this provider to the workspace."}
          </DialogDescription>
          {provider.docs_url && (
            <a
              href={provider.docs_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              View provider docs <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </DialogHeader>

        <div className="space-y-5 p-6 pt-0 sm:p-7 sm:pt-0">
          {provider.unified_mode && (
            <div className="app-inset space-y-3 p-4">
              <div className="flex flex-wrap gap-2">
                {provider.supports_paper && provider.supports_trading && (
                  <Badge variant="info">Paper Trading</Badge>
                )}
                {provider.supports_trading && <Badge variant="success">Live Trading</Badge>}
                {provider.supports_market_data && <Badge variant="primary">Market Data</Badge>}
                {provider.supports_options && <Badge variant="warning">Options</Badge>}
              </div>
              {provider.credential_note && (
                <p className="text-sm leading-6 text-muted-foreground">
                  {provider.credential_note}
                </p>
              )}
            </div>
          )}

          {showPaperToggle && (
            <div className="space-y-2">
              <label className="app-label">Mode</label>
              <div className="flex items-center gap-2">
                <Button
                  onClick={() => setIsPaper(true)}
                  variant={isPaper ? "secondary" : "ghost"}
                  size="sm"
                  className="rounded-full px-4"
                >
                  Paper
                </Button>
                <Button
                  onClick={() => setIsPaper(false)}
                  variant={!isPaper ? "danger" : "ghost"}
                  size="sm"
                  className="rounded-full px-4"
                >
                  Live
                </Button>
              </div>
            </div>
          )}

          {provider.credential_fields.map((field) => (
            <div key={field.key} className="space-y-2">
              <label className="app-label">{field.label}</label>
              <div className="relative">
                <Input
                  type={field.secret && !visibleFields[field.key] ? "password" : "text"}
                  value={credentials[field.key] ?? ""}
                  onChange={(event) =>
                    setCredentials((prev) => ({ ...prev, [field.key]: event.target.value }))
                  }
                  placeholder={
                    isEdit
                      ? `Leave blank to keep existing ${field.label.toLowerCase()}`
                      : `Enter ${field.label.toLowerCase()}`
                  }
                  className="pr-10 font-mono"
                />
                {field.secret && (
                  <button
                    type="button"
                    onClick={() => toggleVisible(field.key)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {visibleFields[field.key] ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                )}
              </div>
            </div>
          ))}

          <div className="space-y-2">
            <label className="app-label">Nickname</label>
            <Input
              value={nickname}
              onChange={(event) => setNickname(event.target.value)}
              placeholder="Optional connection label"
            />
          </div>

          {status === "error" && errorMsg && (
            <p className="text-xs text-red-300">{errorMsg}</p>
          )}
          {status === "success" && (
            <p className="inline-flex items-center gap-1.5 text-xs text-emerald-300">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {isEdit ? "Updated successfully" : "Connection saved"}
            </p>
          )}

          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button onClick={onClose} variant="ghost" size="sm">
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={(!allFilled && !isEdit) || status === "loading" || status === "success"}
              variant="primary"
              size="sm"
            >
              {status === "loading" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {status === "success" && <CheckCircle2 className="h-3.5 w-3.5" />}
              {status === "loading"
                ? isEdit
                  ? "Saving..."
                  : "Connecting..."
                : status === "success"
                  ? isEdit
                    ? "Saved"
                    : "Connected"
                  : isEdit
                    ? "Save Changes"
                    : "Connect"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
