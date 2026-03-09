"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Settings,
  User,
  Sliders,
  Key,
  Loader2,
  Save,
  CheckCircle2,
  XCircle,
  Circle,
  RefreshCw,
  Trash2,
  Plus,
} from "lucide-react";
import Link from "next/link";
import { apiFetch } from "@/lib/api/client";
import { PreferencesForm } from "@/components/settings/PreferencesForm";

const TABS = [
  { id: "profile", label: "Profile", icon: User },
  { id: "preferences", label: "Preferences", icon: Sliders },
  { id: "broker", label: "Broker", icon: Key },
] as const;

type TabId = (typeof TABS)[number]["id"];

function ProfileSection() {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  // Fetch profile on mount
  useEffect(() => {
    apiFetch<{ display_name?: string; email?: string }>("/api/auth/me")
      .then((data) => {
        if (data) {
          setDisplayName(data.display_name || "");
          setEmail(data.email || "");
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaveStatus("idle");
    try {
      const body: Record<string, string> = { display_name: displayName };
      if (currentPassword && newPassword) {
        body.current_password = currentPassword;
        body.new_password = newPassword;
      }
      await apiFetch("/api/auth/profile", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setSaveStatus("success");
      setCurrentPassword("");
      setNewPassword("");
    } catch {
      setSaveStatus("error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <label className="text-xs text-muted-foreground">Email</label>
        <input
          type="email"
          value={email}
          disabled
          className="w-full bg-input/50 border border-border rounded-md px-3 py-2 text-sm font-mono opacity-60 cursor-not-allowed"
        />
        <p className="text-xs text-muted-foreground">Email cannot be changed.</p>
      </div>

      <div className="space-y-1.5">
        <label className="text-xs text-muted-foreground">Display Name</label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Your name..."
          className="w-full bg-input border border-border/50 rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
        />
      </div>

      <div className="border-t pt-4 space-y-3">
        <h4 className="text-sm font-medium">Change Password</h4>
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">Current Password</label>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="w-full bg-input border border-border/50 rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">New Password</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="w-full bg-input border border-border/50 rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
          />
        </div>
      </div>

      {saveStatus === "success" && (
        <p className="text-xs text-emerald-400">Profile updated.</p>
      )}
      {saveStatus === "error" && (
        <p className="text-xs text-red-400">Failed to update profile.</p>
      )}

      <button
        onClick={handleSave}
        disabled={saving || !displayName}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors disabled:opacity-50"
      >
        {saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Save className="h-3.5 w-3.5" />
        )}
        Save Profile
      </button>
    </div>
  );
}

interface BrokerEntry {
  id: number;
  broker_type: string;
  is_paper: boolean;
  nickname?: string;
}

type ConnStatus = "checking" | "connected" | "error" | "idle";

const BROKER_STATUS_ENDPOINT: Record<string, string> = {
  webull: "/api/webull/status",
  alpaca: "/api/trading/account",
};

const BROKER_LABELS: Record<string, string> = {
  webull: "Webull",
  alpaca: "Alpaca",
};

function ConnectionBadge({ status }: { status: ConnStatus }) {
  if (status === "checking") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Checking...
      </span>
    );
  }
  if (status === "connected") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full border border-emerald-400/20">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Connected · Live data active
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full border border-red-400/20">
        <XCircle className="h-3 w-3" />
        Credentials saved · Not connected
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <Circle className="h-3 w-3" />
      Unknown
    </span>
  );
}

function BrokerSection() {
  const [brokers, setBrokers] = useState<BrokerEntry[]>([]);
  const [statuses, setStatuses] = useState<Record<number, ConnStatus>>({});
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<number | null>(null);

  const testBroker = useCallback(async (broker: BrokerEntry) => {
    setStatuses((s) => ({ ...s, [broker.id]: "checking" }));
    try {
      const endpoint = BROKER_STATUS_ENDPOINT[broker.broker_type.toLowerCase()] ?? "/api/trading/account";
      const data = await apiFetch<{ connected?: boolean }>(endpoint);
      setStatuses((s) => ({ ...s, [broker.id]: data?.connected ? "connected" : "error" }));
    } catch {
      setStatuses((s) => ({ ...s, [broker.id]: "error" }));
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const me = await apiFetch<{ brokers?: BrokerEntry[] }>("/api/auth/me");
      const list = me.brokers ?? [];
      setBrokers(list);
      // Test all in parallel
      await Promise.all(list.map(testBroker));
    } catch {
      setBrokers([]);
    } finally {
      setLoading(false);
    }
  }, [testBroker]);

  useEffect(() => { load(); }, [load]);

  const handleRemove = async (cred: BrokerEntry) => {
    setRemoving(cred.id);
    try {
      await apiFetch(`/api/auth/broker-credentials/${cred.id}`, { method: "DELETE" });
      setBrokers((b) => b.filter((x) => x.id !== cred.id));
      setStatuses((s) => { const n = { ...s }; delete n[cred.id]; return n; });
    } catch {
      // keep as-is on error
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold">Connected Brokers</h4>
          <p className="text-xs text-muted-foreground mt-0.5">
            API keys are encrypted at rest. Live indicators verify real-time connectivity.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="p-1.5 rounded-md border border-border/50 text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors disabled:opacity-40"
            title="Refresh all statuses"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
          <Link
            href="/settings/broker"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add / Update
          </Link>
        </div>
      </div>

      {loading && brokers.length === 0 ? (
        <div className="flex items-center justify-center py-10">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : brokers.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/50 p-8 text-center space-y-2">
          <Key className="h-8 w-8 text-muted-foreground/30 mx-auto" />
          <p className="text-sm text-muted-foreground">No brokers configured yet.</p>
          <Link
            href="/settings/broker"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary/90 transition-colors mt-1"
          >
            <Plus className="h-3.5 w-3.5" />
            Connect a Broker
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {brokers.map((broker) => {
            const status = statuses[broker.id] ?? "idle";
            const label = BROKER_LABELS[broker.broker_type.toLowerCase()] ?? broker.broker_type;
            return (
              <div
                key={broker.id}
                className="rounded-lg border border-border/50 bg-card/50 p-4 flex items-center gap-4"
              >
                {/* Status dot */}
                <div className={`h-9 w-9 rounded-lg flex items-center justify-center shrink-0 ${
                  status === "connected"
                    ? "bg-emerald-400/10"
                    : status === "error"
                    ? "bg-red-400/10"
                    : "bg-muted/50"
                }`}>
                  {status === "connected" ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                  ) : status === "error" ? (
                    <XCircle className="h-5 w-5 text-red-400" />
                  ) : (
                    <Key className="h-5 w-5 text-muted-foreground/50" />
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold">{label}</span>
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                      broker.is_paper
                        ? "text-muted-foreground border-border/50 bg-muted/30"
                        : "text-emerald-400 border-emerald-400/30 bg-emerald-400/10"
                    }`}>
                      {broker.is_paper ? "PAPER" : "LIVE"}
                    </span>
                    {broker.nickname && (
                      <span className="text-xs text-muted-foreground font-mono">{broker.nickname}</span>
                    )}
                  </div>
                  <div className="mt-1">
                    <ConnectionBadge status={status} />
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => testBroker(broker)}
                    disabled={status === "checking"}
                    className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors disabled:opacity-40"
                    title="Re-test connection"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${status === "checking" ? "animate-spin" : ""}`} />
                  </button>
                  <button
                    onClick={() => handleRemove(broker)}
                    disabled={removing === broker.id}
                    className="p-1.5 rounded-md text-muted-foreground hover:text-red-400 hover:bg-red-400/10 border border-border/50 transition-colors disabled:opacity-40"
                    title="Disconnect broker"
                  >
                    {removing === broker.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("profile");

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Settings className="h-5 w-5 text-primary" />
        <h2 className="text-xl font-semibold">Settings</h2>
      </div>

      <div className="flex gap-6">
        {/* Tab sidebar */}
        <div className="flex flex-col gap-1 min-w-[160px]">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors ${
                  activeTab === tab.id
                    ? "bg-muted text-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        <div className="flex-1 rounded-lg border border-border/50 bg-card p-6 min-h-[400px]">
          {activeTab === "profile" && <ProfileSection />}
          {activeTab === "preferences" && <PreferencesForm />}
          {activeTab === "broker" && <BrokerSection />}
        </div>
      </div>
    </div>
  );
}
