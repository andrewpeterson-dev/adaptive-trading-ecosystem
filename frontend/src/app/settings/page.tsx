"use client";

import { useState } from "react";
import {
  Settings,
  User,
  Sliders,
  Plug,
  Loader2,
  Save,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { PreferencesForm } from "@/components/settings/PreferencesForm";
import { ApiConnectionsSection } from "@/components/settings/ApiConnectionsSection";
import { useEffect } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { cn } from "@/lib/utils";

const TABS = [
  { id: "profile",     label: "Profile",      icon: User },
  { id: "preferences", label: "Preferences",  icon: Sliders },
  { id: "connections", label: "Connections",  icon: Plug },
] as const;

type TabId = (typeof TABS)[number]["id"];

// ─── Profile tab ──────────────────────────────────────────────────────────────

function ProfileSection() {
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");

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
      <div className="space-y-2">
        <label className="app-label">Email</label>
        <input
          type="email"
          value={email}
          disabled
          className="app-input cursor-not-allowed font-mono opacity-60"
        />
        <p className="text-xs text-muted-foreground">Email cannot be changed.</p>
      </div>

      <div className="space-y-2">
        <label className="app-label">Display Name</label>
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Your name..."
          className="app-input"
        />
      </div>

      <div className="app-inset p-4 sm:p-5 space-y-4">
        <div>
          <p className="text-sm font-semibold text-foreground">Change Password</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Leave these fields blank unless you want to rotate your password.
          </p>
        </div>

        <div className="space-y-2">
          <label className="app-label">Current Password</label>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="app-input"
          />
        </div>

        <div className="space-y-2">
          <label className="app-label">New Password</label>
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="app-input"
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
        className="app-button-primary disabled:translate-y-0 disabled:opacity-50"
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>("profile");

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Preferences"
        title="Settings"
        description="Manage your account identity, product behavior, and external connections from a cleaner control surface."
        badge={
          <span className="app-pill">
            <Settings className="h-3.5 w-3.5" />
            Workspace
          </span>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="app-panel p-3">
          <div className="flex gap-2 overflow-x-auto lg:flex-col">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex min-w-fit items-center gap-2 rounded-2xl px-4 py-3 text-sm text-left transition-all lg:w-full",
                    active
                      ? "bg-foreground text-background shadow-[0_18px_32px_-24px_rgba(15,23,42,0.6)]"
                      : "text-muted-foreground hover:bg-black/[0.04] hover:text-foreground dark:hover:bg-white/[0.05]"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        <div
          className={cn(
            "app-panel min-h-[420px]",
            activeTab === "connections" ? "p-4 sm:p-5" : "p-6 sm:p-7"
          )}
        >
          {activeTab === "profile" && <ProfileSection />}
          {activeTab === "preferences" && <PreferencesForm />}
          {activeTab === "connections" && <ApiConnectionsSection />}
        </div>
      </div>
    </div>
  );
}
