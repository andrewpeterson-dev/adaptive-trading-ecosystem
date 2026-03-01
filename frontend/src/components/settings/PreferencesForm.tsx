"use client";

import { useState } from "react";
import { Save, Loader2, X } from "lucide-react";

interface Preferences {
  default_symbols: string[];
  notify_risk_alerts: boolean;
  notify_trade_executions: boolean;
  notify_model_retraining: boolean;
  trading_mode: "paper" | "live";
  refresh_interval: number;
}

const REFRESH_OPTIONS = [
  { value: 15, label: "15 seconds" },
  { value: 30, label: "30 seconds" },
  { value: 60, label: "1 minute" },
  { value: 300, label: "5 minutes" },
];

export function PreferencesForm() {
  const [prefs, setPrefs] = useState<Preferences>({
    default_symbols: ["SPY", "QQQ", "AAPL"],
    notify_risk_alerts: true,
    notify_trade_executions: true,
    notify_model_retraining: false,
    trading_mode: "paper",
    refresh_interval: 60,
  });
  const [symbolInput, setSymbolInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");

  const addSymbol = () => {
    const symbol = symbolInput.trim().toUpperCase();
    if (symbol && !prefs.default_symbols.includes(symbol)) {
      setPrefs((p) => ({
        ...p,
        default_symbols: [...p.default_symbols, symbol],
      }));
    }
    setSymbolInput("");
  };

  const removeSymbol = (sym: string) => {
    setPrefs((p) => ({
      ...p,
      default_symbols: p.default_symbols.filter((s) => s !== sym),
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
      const res = await fetch("/api/auth/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(prefs),
      });
      setSaveStatus(res.ok ? "success" : "error");
    } catch {
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Default Symbols */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Default Watchlist Symbols</label>
        <div className="flex flex-wrap gap-1.5 mb-2">
          {prefs.default_symbols.map((sym) => (
            <span
              key={sym}
              className="inline-flex items-center gap-1 text-xs font-mono bg-muted px-2 py-1 rounded"
            >
              {sym}
              <button
                onClick={() => removeSymbol(sym)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={symbolInput}
            onChange={(e) => setSymbolInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add symbol (e.g. TSLA)..."
            className="flex-1 bg-input border border-border rounded-md px-3 py-1.5 text-sm font-mono placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <button
            onClick={addSymbol}
            disabled={!symbolInput.trim()}
            className="px-3 py-1.5 text-sm rounded-md border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>

      {/* Notifications */}
      <div className="space-y-3">
        <label className="text-sm font-medium">Notifications</label>
        <div className="space-y-2">
          {[
            { key: "notify_risk_alerts" as const, label: "Risk alerts" },
            { key: "notify_trade_executions" as const, label: "Trade executions" },
            { key: "notify_model_retraining" as const, label: "Model retraining" },
          ].map((item) => (
            <label
              key={item.key}
              className="flex items-center gap-3 cursor-pointer"
            >
              <button
                onClick={() =>
                  setPrefs((p) => ({ ...p, [item.key]: !p[item.key] }))
                }
                className={`relative h-5 w-9 rounded-full transition-colors ${
                  prefs[item.key] ? "bg-primary" : "bg-muted"
                }`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                    prefs[item.key] ? "translate-x-4" : "translate-x-0.5"
                  }`}
                />
              </button>
              <span className="text-sm">{item.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Trading Mode */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Trading Mode</label>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setPrefs((p) => ({ ...p, trading_mode: "paper" }))}
            className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
              prefs.trading_mode === "paper"
                ? "bg-primary/10 text-primary border-primary/30"
                : "text-muted-foreground border-border hover:bg-muted"
            }`}
          >
            Paper Trading
          </button>
          <button
            onClick={() => setPrefs((p) => ({ ...p, trading_mode: "live" }))}
            className={`px-3 py-1.5 text-xs rounded-md border transition-colors ${
              prefs.trading_mode === "live"
                ? "bg-red-500/10 text-red-400 border-red-500/30"
                : "text-muted-foreground border-border hover:bg-muted"
            }`}
          >
            Live Trading
          </button>
        </div>
      </div>

      {/* Refresh Interval */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Data Refresh Interval</label>
        <select
          value={prefs.refresh_interval}
          onChange={(e) =>
            setPrefs((p) => ({ ...p, refresh_interval: Number(e.target.value) }))
          }
          className="bg-input border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
        >
          {REFRESH_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Save */}
      {saveStatus === "success" && (
        <p className="text-xs text-emerald-400">Preferences saved.</p>
      )}
      {saveStatus === "error" && (
        <p className="text-xs text-red-400">Failed to save preferences.</p>
      )}
      <button
        onClick={handleSave}
        disabled={saving}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
      >
        {saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Save className="h-3.5 w-3.5" />
        )}
        Save Preferences
      </button>
    </div>
  );
}
