"use client";

import { useState, useEffect } from "react";
import { Save, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";

interface Preferences {
  default_symbols: string[];
  notify_risk_alerts: boolean;
  notify_trade_executions: boolean;
  notify_model_retraining: boolean;
  trading_mode: "paper" | "live";
  refresh_interval: number;
}

const REFRESH_OPTIONS = [
  { value: 1, label: "1 second" },
  { value: 5, label: "5 seconds" },
  { value: 15, label: "15 seconds" },
  { value: 30, label: "30 seconds" },
  { value: 60, label: "1 minute" },
  { value: 300, label: "5 minutes" },
];

const PREFS_KEY = "trading_preferences";

const DEFAULT_PREFS: Preferences = {
  default_symbols: ["SPY", "QQQ", "AAPL"],
  notify_risk_alerts: true,
  notify_trade_executions: true,
  notify_model_retraining: false,
  trading_mode: "paper",
  refresh_interval: 60,
};

export function PreferencesForm() {
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS);
  const [symbolInput, setSymbolInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">(
    "idle"
  );

  useEffect(() => {
    try {
      const stored = localStorage.getItem(PREFS_KEY);
      if (stored) {
        setPrefs({ ...DEFAULT_PREFS, ...JSON.parse(stored) });
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  const addSymbol = () => {
    const symbol = symbolInput.trim().toUpperCase();
    if (symbol && !prefs.default_symbols.includes(symbol)) {
      setPrefs((current) => ({
        ...current,
        default_symbols: [...current.default_symbols, symbol],
      }));
    }
    setSymbolInput("");
  };

  const removeSymbol = (symbol: string) => {
    setPrefs((current) => ({
      ...current,
      default_symbols: current.default_symbols.filter((value) => value !== symbol),
    }));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addSymbol();
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveStatus("idle");
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
      setSaveStatus("success");
    } catch {
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div>
          <p className="app-label">Default Watchlist</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Seed the workspace with the names you monitor every day.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {prefs.default_symbols.map((symbol) => (
            <Badge
              key={symbol}
              className="gap-2 px-3 py-1.5 tracking-normal font-mono"
            >
              {symbol}
              <button
                onClick={() => removeSymbol(symbol)}
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            type="text"
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add symbol (e.g. TSLA)"
            className="font-mono sm:max-w-xs"
          />
          <Button
            variant="secondary"
            size="sm"
            onClick={addSymbol}
            disabled={!symbolInput.trim()}
          >
            Add symbol
          </Button>
        </div>
      </section>

      <section className="app-inset p-4 sm:p-5">
        <div className="space-y-4">
          <div>
            <p className="app-label">Notifications</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose which operational events should interrupt you.
            </p>
          </div>
          <div className="space-y-4">
            {[
              {
                key: "notify_risk_alerts" as const,
                label: "Risk alerts",
                description: "Halt conditions, drawdown breaches, and policy violations.",
              },
              {
                key: "notify_trade_executions" as const,
                label: "Trade executions",
                description: "Filled orders, cancellations, and execution-side feedback.",
              },
              {
                key: "notify_model_retraining" as const,
                label: "Model retraining",
                description: "New learning cycles, refreshed weights, and ensemble changes.",
              },
            ].map((item) => (
              <label
                key={item.key}
                className="flex items-start justify-between gap-4 rounded-[18px] border border-border/70 bg-muted/30 p-4"
              >
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">{item.label}</p>
                  <p className="text-sm leading-6 text-muted-foreground">
                    {item.description}
                  </p>
                </div>
                <Switch
                  checked={prefs[item.key]}
                  onClick={() =>
                    setPrefs((current) => ({
                      ...current,
                      [item.key]: !current[item.key],
                    }))
                  }
                />
              </label>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="app-inset p-4 sm:p-5">
          <div className="space-y-3">
            <div>
              <p className="app-label">Trading Mode</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Set the default environment for new sessions.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant={prefs.trading_mode === "paper" ? "primary" : "secondary"}
                size="sm"
                onClick={() =>
                  setPrefs((current) => ({ ...current, trading_mode: "paper" }))
                }
              >
                Paper Trading
              </Button>
              <Button
                variant={prefs.trading_mode === "live" ? "danger" : "secondary"}
                size="sm"
                onClick={() =>
                  setPrefs((current) => ({ ...current, trading_mode: "live" }))
                }
              >
                Live Trading
              </Button>
            </div>
          </div>
        </div>

        <div className="app-inset p-4 sm:p-5">
          <div className="space-y-3">
            <div>
              <p className="app-label">Refresh Interval</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Control how aggressively the UI polls for updates.
              </p>
            </div>
            <Select
              value={prefs.refresh_interval}
              onChange={(e) =>
                setPrefs((current) => ({
                  ...current,
                  refresh_interval: Number(e.target.value),
                }))
              }
              className="sm:max-w-xs"
            >
              {REFRESH_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </div>
        </div>
      </section>

      {saveStatus === "success" && (
        <p className="text-xs text-emerald-300">Preferences saved.</p>
      )}
      {saveStatus === "error" && (
        <p className="text-xs text-red-300">Failed to save preferences.</p>
      )}

      <Button variant="primary" onClick={handleSave} disabled={saving}>
        {saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Save className="h-3.5 w-3.5" />
        )}
        Save Preferences
      </Button>
    </div>
  );
}
