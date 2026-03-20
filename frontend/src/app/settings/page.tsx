"use client";

import { useState } from "react";
import {
  Settings,
  User,
  SlidersHorizontal,
  Plug,
  Loader2,
  Save,
  Lock,
  ChevronDown,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { PreferencesForm } from "@/components/settings/PreferencesForm";
import { ApiConnectionsSection } from "@/components/settings/ApiConnectionsSection";
import { useEffect } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

const TABS = [
  { id: "profile",     label: "Profile",      icon: User },
  { id: "preferences", label: "Preferences",  icon: SlidersHorizontal },
  { id: "connections", label: "Connections",  icon: Plug },
] as const;

type TabId = (typeof TABS)[number]["id"];

// ─── Profile tab ──────────────────────────────────────────────────────────────

function ProfileSection() {
  const { toast } = useToast();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [showPasswordSection, setShowPasswordSection] = useState(false);
  const [showDangerZone, setShowDangerZone] = useState(false);

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
      toast("Profile saved", "success");
      setCurrentPassword("");
      setNewPassword("");
    } catch {
      toast("Failed to update profile", "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-5 pb-20 lg:pb-0">
      <div className="app-panel p-5 space-y-5">
        <div className="space-y-2">
          <label className="app-label">Email</label>
          <Input
            type="email"
            value={email}
            disabled
            className="app-input cursor-not-allowed font-mono opacity-60"
          />
          <p className="text-xs text-muted-foreground mt-1">
            To update your email, <a href="mailto:support@adaptivetrading.com" className="text-primary hover:underline">contact support →</a>
          </p>
        </div>

        <div className="space-y-2">
          <label className="app-label">Display Name</label>
          <Input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your name..."
          />
        </div>
      </div>

      <div className="app-panel overflow-hidden mt-4">
        <button
          onClick={() => setShowPasswordSection((prev) => !prev)}
          className="flex w-full items-center justify-between px-5 py-4 text-sm font-semibold text-foreground hover:bg-muted/20 transition-colors"
        >
          <span className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-muted-foreground" />
            Change Password
          </span>
          <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", showPasswordSection && "rotate-180")} />
        </button>
        {showPasswordSection && (
          <div className="border-t border-border/50 px-5 py-4 space-y-4">
            <p className="text-sm text-muted-foreground">
              Leave these fields blank unless you want to rotate your password.
            </p>

            <div className="space-y-2">
              <label className="app-label">Current Password</label>
              <Input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <label className="app-label">New Password</label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
          </div>
        )}
      </div>

      <Button
        onClick={handleSave}
        disabled={saving || !displayName}
        variant="primary"
      >
        {saving ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Save className="h-3.5 w-3.5" />
        )}
        Save Profile
      </Button>

      {/* Danger Zone */}
      <div className="mt-8">
        <button
          onClick={() => setShowDangerZone((prev) => !prev)}
          className="flex items-center gap-2 text-sm text-red-400 hover:text-red-300 transition-colors"
        >
          <ChevronDown className={cn("h-4 w-4 transition-transform", showDangerZone && "rotate-180")} />
          Danger Zone
        </button>
        {showDangerZone && (
          <div className="mt-4 space-y-3 rounded-xl border border-red-500/20 bg-red-500/5 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-red-400">Delete Account</p>
                <p className="text-xs text-muted-foreground">Permanently delete your account and all data</p>
              </div>
              <button
                onClick={() => {
                  if (confirm("Are you sure you want to delete your account? This action is permanent and cannot be undone.")) {
                    toast("Contact support to delete your account: support@adaptivetrading.com", "info");
                  }
                }}
                className="rounded-full border border-red-500/25 bg-red-500/12 px-4 py-2 text-xs font-semibold text-red-400 hover:bg-red-500/20 transition-colors"
              >
                Delete Account
              </button>
            </div>
            <div className="border-t border-red-500/10" />
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-red-400">Reset Workspace</p>
                <p className="text-xs text-muted-foreground">Clear all strategies, bots, and settings</p>
              </div>
              <button
                onClick={() => {
                  if (confirm("Are you sure you want to reset your workspace? All strategies, bots, and settings will be cleared.")) {
                    toast("Contact support to reset your workspace: support@adaptivetrading.com", "info");
                  }
                }}
                className="rounded-full border border-red-500/25 bg-red-500/12 px-4 py-2 text-xs font-semibold text-red-400 hover:bg-red-500/20 transition-colors"
              >
                Reset
              </button>
            </div>
          </div>
        )}
      </div>
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
        <div className="app-panel p-3 lg:min-h-[280px]">
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
                      ? "app-card text-foreground shadow-none"
                      : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
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
