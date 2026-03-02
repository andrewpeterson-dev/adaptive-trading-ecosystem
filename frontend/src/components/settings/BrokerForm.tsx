"use client";

import { useState, useEffect } from "react";
import {
  Eye,
  EyeOff,
  Loader2,
  CheckCircle2,
  XCircle,
  Plug,
  Save,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";

type BrokerType = "alpaca" | "webull";

interface BrokerFormProps {
  broker: BrokerType;
}

interface FormState {
  api_key: string;
  api_secret: string;
  base_url: string;
  is_paper: boolean;
}

const DEFAULT_URLS: Record<BrokerType, string> = {
  alpaca: "https://paper-api.alpaca.markets",
  webull: "",
};

export function BrokerForm({ broker }: BrokerFormProps) {
  const [form, setForm] = useState<FormState>({
    api_key: "",
    api_secret: "",
    base_url: DEFAULT_URLS[broker],
    is_paper: true,
  });
  const [showKey, setShowKey] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const [testStatus, setTestStatus] = useState<"idle" | "connected" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");

  // Reset form when switching broker type
  useEffect(() => {
    setForm({ api_key: "", api_secret: "", base_url: DEFAULT_URLS[broker], is_paper: true });
    setSaveStatus("idle");
    setTestStatus("idle");
    setErrorMsg("");
  }, [broker]);

  const handleSave = async () => {
    setSaving(true);
    setSaveStatus("idle");
    setErrorMsg("");
    try {
      await apiFetch("/api/auth/broker-credentials", {
        method: "POST",
        body: JSON.stringify({
          broker_type: broker,
          api_key: form.api_key,
          api_secret: form.api_secret,
          base_url: form.base_url,
          is_paper: form.is_paper,
        }),
      });
      setSaveStatus("success");
      setForm((f) => ({ ...f, api_key: "", api_secret: "" }));
    } catch (err) {
      setSaveStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Failed to save credentials");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestStatus("idle");
    setErrorMsg("");
    try {
      const endpoint = broker === "webull" ? "/api/webull/status" : "/api/trading/account";
      const data = await apiFetch<{ connected?: boolean }>(endpoint);
      if (data?.connected) {
        setTestStatus("connected");
      } else {
        setTestStatus("error");
        setErrorMsg("Credentials saved but broker returned not connected — verify API key and secret");
      }
    } catch (err) {
      setTestStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Cannot reach trading API");
    } finally {
      setTesting(false);
    }
  };

  const updateUrl = (isPaper: boolean) => {
    if (broker === "alpaca") {
      setForm((f) => ({
        ...f,
        is_paper: isPaper,
        base_url: isPaper
          ? "https://paper-api.alpaca.markets"
          : "https://api.alpaca.markets",
      }));
    } else {
      setForm((f) => ({ ...f, is_paper: isPaper }));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold capitalize">{broker} Credentials</h4>
        {testStatus === "connected" && (
          <span className="inline-flex items-center gap-1 text-xs text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded">
            <CheckCircle2 className="h-3 w-3" />
            Connected
          </span>
        )}
        {testStatus === "error" && (
          <span className="inline-flex items-center gap-1 text-xs text-red-400 bg-red-400/10 px-2 py-0.5 rounded">
            <XCircle className="h-3 w-3" />
            Disconnected
          </span>
        )}
      </div>

      {/* Paper/Live toggle */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => updateUrl(true)}
          className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
            form.is_paper
              ? "bg-primary/10 text-primary border-primary/30"
              : "text-muted-foreground border-border hover:bg-muted"
          }`}
        >
          Paper
        </button>
        <button
          onClick={() => updateUrl(false)}
          className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
            !form.is_paper
              ? "bg-red-500/10 text-red-400 border-red-500/30"
              : "text-muted-foreground border-border hover:bg-muted"
          }`}
        >
          Live
        </button>
      </div>

      {/* API Key */}
      <div className="space-y-1.5">
        <label className="text-xs text-muted-foreground">API Key</label>
        <div className="relative">
          <input
            type={showKey ? "text" : "password"}
            value={form.api_key}
            onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))}
            placeholder="Enter API key..."
            className="w-full bg-input border border-border/50 rounded-md px-3 py-2 pr-9 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            {showKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* API Secret */}
      <div className="space-y-1.5">
        <label className="text-xs text-muted-foreground">API Secret</label>
        <div className="relative">
          <input
            type={showSecret ? "text" : "password"}
            value={form.api_secret}
            onChange={(e) => setForm((f) => ({ ...f, api_secret: e.target.value }))}
            placeholder="Enter API secret..."
            className="w-full bg-input border border-border/50 rounded-md px-3 py-2 pr-9 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
          />
          <button
            type="button"
            onClick={() => setShowSecret(!showSecret)}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            {showSecret ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Base URL — only for Alpaca (Webull SDK manages its own endpoints) */}
      {broker === "alpaca" && (
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">Base URL</label>
          <input
            type="text"
            value={form.base_url}
            onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
            placeholder="https://..."
            className="w-full bg-input border border-border/50 rounded-md px-3 py-2 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
          />
        </div>
      )}

      {/* Feedback */}
      {saveStatus === "success" && (
        <p className="text-xs text-emerald-400">Credentials saved and encrypted.</p>
      )}
      {(saveStatus === "error" || testStatus === "error") && errorMsg && (
        <p className="text-xs text-red-400">{errorMsg}</p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={handleSave}
          disabled={saving || !form.api_key || !form.api_secret}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {saving ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Save className="h-3.5 w-3.5" />
          )}
          Save
        </button>
        <button
          onClick={handleTest}
          disabled={testing}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border/50 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors disabled:opacity-50"
        >
          {testing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plug className="h-3.5 w-3.5" />
          )}
          Test Connection
        </button>
      </div>
    </div>
  );
}
