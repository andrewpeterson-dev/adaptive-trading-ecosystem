"use client";

import { useState } from "react";
import { Settings, User, Sliders, Key, Loader2, Save } from "lucide-react";
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
  const [loaded, setLoaded] = useState(false);

  // Fetch profile on first render
  if (!loaded) {
    setLoaded(true);
    fetch("/api/auth/me")
      .then((res) => {
        if (res.ok) return res.json();
        return null;
      })
      .then((data) => {
        if (data) {
          setDisplayName(data.display_name || "");
          setEmail(data.email || "");
        }
      })
      .catch(() => {});
  }

  const handleSave = async () => {
    setSaving(true);
    setSaveStatus("idle");
    try {
      const body: Record<string, string> = { display_name: displayName };
      if (currentPassword && newPassword) {
        body.current_password = currentPassword;
        body.new_password = newPassword;
      }
      const res = await fetch("/api/auth/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setSaveStatus("success");
        setCurrentPassword("");
        setNewPassword("");
      } else {
        setSaveStatus("error");
      }
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
          className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
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
            className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-muted-foreground">New Password</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="w-full bg-input border border-border rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
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
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
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

function BrokerRedirect() {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Manage your broker API credentials and connection settings.
      </p>
      <a
        href="/settings/broker"
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
      >
        <Key className="h-3.5 w-3.5" />
        Broker Settings
      </a>
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
        <div className="flex-1 rounded-lg border bg-card p-6 min-h-[400px]">
          {activeTab === "profile" && <ProfileSection />}
          {activeTab === "preferences" && <PreferencesForm />}
          {activeTab === "broker" && <BrokerRedirect />}
        </div>
      </div>
    </div>
  );
}
