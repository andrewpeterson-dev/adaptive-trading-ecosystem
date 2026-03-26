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
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

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
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">(
    "idle"
  );
  const [testStatus, setTestStatus] = useState<"idle" | "connected" | "error">(
    "idle"
  );
  const [errorMsg, setErrorMsg] = useState("");
  const [hasSavedCreds, setHasSavedCreds] = useState(false);

  useEffect(() => {
    setForm({
      api_key: "",
      api_secret: "",
      base_url: DEFAULT_URLS[broker],
      is_paper: true,
    });
    setSaveStatus("idle");
    setTestStatus("idle");
    setErrorMsg("");
    setHasSavedCreds(false);

    (async () => {
      try {
        const me = await apiFetch<{
          brokers?: { broker_type: string; is_paper: boolean }[];
        }>("/api/auth/me");
        const match = me.brokers?.find(
          (entry) => entry.broker_type.toLowerCase() === broker
        );
        if (match) {
          setHasSavedCreds(true);
          setForm((current) => ({ ...current, is_paper: match.is_paper }));
          const endpoint =
            broker === "webull" ? "/api/webull/status" : "/api/trading/account";
          const data = await apiFetch<{ connected?: boolean }>(endpoint);
          setTestStatus(data?.connected ? "connected" : "error");
        }
      } catch {
        // ignore auth or API issues here
      }
    })();
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
      setForm((current) => ({ ...current, api_key: "", api_secret: "" }));
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
      const endpoint =
        broker === "webull" ? "/api/webull/status" : "/api/trading/account";
      const data = await apiFetch<{ connected?: boolean }>(endpoint);
      if (data?.connected) {
        setTestStatus("connected");
      } else {
        setTestStatus("error");
        setErrorMsg(
          "Credentials saved but the broker still reports disconnected access."
        );
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
      setForm((current) => ({
        ...current,
        is_paper: isPaper,
        base_url: isPaper
          ? "https://paper-api.alpaca.markets"
          : "https://api.alpaca.markets",
      }));
    } else {
      setForm((current) => ({ ...current, is_paper: isPaper }));
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="app-label">{broker} Connection</p>
          <h3 className="mt-2 text-lg font-semibold capitalize text-foreground">
            {broker} credentials
          </h3>
        </div>
        {testStatus === "connected" && (
          <Badge variant="positive">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Connected
          </Badge>
        )}
        {testStatus === "error" && (
          <Badge variant="negative">
            <XCircle className="h-3.5 w-3.5" />
            Disconnected
          </Badge>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          variant={form.is_paper ? "primary" : "secondary"}
          size="sm"
          onClick={() => updateUrl(true)}
        >
          Paper
        </Button>
        <Button
          variant={!form.is_paper ? "danger" : "secondary"}
          size="sm"
          onClick={() => updateUrl(false)}
        >
          Live
        </Button>
      </div>

      <section className="grid gap-4">
        <div className="space-y-2">
          <label className="app-label">API Key</label>
          <div className="relative">
            <Input
              type={showKey ? "text" : "password"}
              value={form.api_key}
              onChange={(e) =>
                setForm((current) => ({ ...current, api_key: e.target.value }))
              }
              placeholder={
                hasSavedCreds ? "Saved. Enter a new key to rotate it." : "Enter API key"
              }
              className="pr-10 font-mono"
            />
            <button
              type="button"
              onClick={() => setShowKey((current) => !current)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
            >
              {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <div className="space-y-2">
          <label className="app-label">API Secret</label>
          <div className="relative">
            <Input
              type={showSecret ? "text" : "password"}
              value={form.api_secret}
              onChange={(e) =>
                setForm((current) => ({ ...current, api_secret: e.target.value }))
              }
              placeholder={
                hasSavedCreds
                  ? "Saved. Enter a new secret to rotate it."
                  : "Enter API secret"
              }
              className="pr-10 font-mono"
            />
            <button
              type="button"
              onClick={() => setShowSecret((current) => !current)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
            >
              {showSecret ? (
                <EyeOff className="h-4 w-4" />
              ) : (
                <Eye className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>

        {broker === "alpaca" && (
          <div className="space-y-2">
            <label className="app-label">Base URL</label>
            <Input
              type="text"
              value={form.base_url}
              onChange={(e) =>
                setForm((current) => ({ ...current, base_url: e.target.value }))
              }
              placeholder="https://..."
              className="font-mono"
            />
          </div>
        )}
      </section>

      <div className="app-inset p-4 sm:p-5">
        <div className="space-y-2">
          <p className="app-label">Connection Notes</p>
          <p className="text-sm leading-6 text-muted-foreground">
            Credentials are encrypted at rest. Paper mode points to your simulation
            environment and live mode points to the broker production endpoint.
          </p>
        </div>
      </div>

      {saveStatus === "success" && (
        <p className="text-xs text-emerald-500 dark:text-emerald-400">Credentials saved and encrypted.</p>
      )}
      {(saveStatus === "error" || testStatus === "error") && errorMsg && (
        <p className="text-xs text-red-500 dark:text-red-400">{errorMsg}</p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="primary"
          onClick={handleSave}
          disabled={saving || !form.api_key || !form.api_secret}
        >
          {saving ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Save className="h-3.5 w-3.5" />
          )}
          Save Credentials
        </Button>
        <Button variant="secondary" onClick={handleTest} disabled={testing}>
          {testing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plug className="h-3.5 w-3.5" />
          )}
          Test Connection
        </Button>
      </div>
    </div>
  );
}
