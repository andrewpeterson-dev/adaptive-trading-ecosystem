"use client";

import { useEffect, useState } from "react";
import { Shield, Loader2, Lock } from "lucide-react";
import { PlatformStats } from "@/components/admin/PlatformStats";
import { UserTable } from "@/components/admin/UserTable";
import type { SystemHealth } from "@/types/admin";

function SystemHealthIndicators() {
  const [services, setServices] = useState<SystemHealth[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchHealth() {
      try {
        const [healthRes, configRes] = await Promise.allSettled([
          fetch("/health"),
          fetch("/api/system/config"),
        ]);

        const result: SystemHealth[] = [];

        if (healthRes.status === "fulfilled" && healthRes.value.ok) {
          const data = await healthRes.value.json();
          result.push({
            service: "API Server",
            status: data.status === "healthy" ? "healthy" : "degraded",
            last_check: new Date().toISOString(),
          });
          result.push({
            service: "Trading Mode",
            status: "healthy",
            uptime: data.mode?.toUpperCase(),
          });
        } else {
          result.push({ service: "API Server", status: "down" });
        }

        if (configRes.status === "fulfilled" && configRes.value.ok) {
          result.push({ service: "Config", status: "healthy" });
        } else {
          result.push({ service: "Config", status: "degraded" });
        }

        setServices(result);
      } catch {
        setServices([{ service: "API Server", status: "down" }]);
      } finally {
        setLoading(false);
      }
    }
    fetchHealth();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const statusColor: Record<string, string> = {
    healthy: "bg-emerald-400",
    degraded: "bg-amber-400",
    down: "bg-red-400",
  };

  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-semibold mb-3">System Health</h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {services.map((svc) => (
          <div
            key={svc.service}
            className="flex items-center gap-3 rounded-md border border-border/50 px-3 py-2"
          >
            <div
              className={`h-2 w-2 rounded-full ${statusColor[svc.status] || "bg-muted-foreground"}`}
            />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{svc.service}</div>
              {svc.uptime && (
                <div className="text-xs text-muted-foreground">{svc.uptime}</div>
              )}
            </div>
            <span className="text-xs text-muted-foreground capitalize">
              {svc.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AdminPage() {
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function checkAdmin() {
      try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
          const user = await res.json();
          setIsAdmin(user.is_admin === true);
        } else {
          // If auth endpoint doesn't exist yet, allow access in dev
          setIsAdmin(true);
        }
      } catch {
        // Fallback: allow access when backend isn't running auth
        setIsAdmin(true);
      } finally {
        setLoading(false);
      }
    }
    checkAdmin();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isAdmin === false) {
    return (
      <div className="text-center py-20 space-y-3">
        <Lock className="h-10 w-10 text-muted-foreground/40 mx-auto" />
        <h2 className="text-lg font-semibold">Access Denied</h2>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          You do not have admin privileges. Contact an administrator to request access.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Shield className="h-5 w-5 text-primary" />
        <h2 className="text-xl font-semibold">Admin Panel</h2>
      </div>

      <PlatformStats />
      <UserTable />
      <SystemHealthIndicators />
    </div>
  );
}
