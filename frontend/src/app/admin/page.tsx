"use client";

import { useEffect, useState } from "react";
import { Shield, Loader2, Lock } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { PlatformStats } from "@/components/admin/PlatformStats";
import { UserTable } from "@/components/admin/UserTable";
import type { SystemHealth } from "@/types/admin";

function normalizeStatus(status?: string): SystemHealth["status"] {
  if (status === "healthy" || status === "up" || status === "ok") {
    return "healthy";
  }
  if (status === "unhealthy" || status === "down" || status === "critical") {
    return "down";
  }
  return "degraded";
}

function SystemHealthIndicators() {
  const [services, setServices] = useState<SystemHealth[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchHealth() {
      try {
        const [healthRes, configRes] = await Promise.allSettled([
          apiFetch<any>("/api/system/health/detailed"),
          apiFetch<any>("/api/system/config"),
        ]);

        const result: SystemHealth[] = [];

        if (healthRes.status === "fulfilled") {
          const data = healthRes.value;
          result.push({
            service: "API Server",
            status: normalizeStatus(data.checks?.api?.status ?? data.status),
            last_check: data.timestamp ?? new Date().toISOString(),
          });
          result.push({
            service: "Database",
            status: normalizeStatus(data.checks?.database?.status ?? data.status),
            last_check: data.timestamp ?? new Date().toISOString(),
          });
          result.push({
            service: "Redis",
            status: normalizeStatus(data.checks?.redis?.status ?? data.status),
            last_check: data.timestamp ?? new Date().toISOString(),
          });
        } else {
          result.push({ service: "API Server", status: "down" });
        }

        if (configRes.status === "fulfilled") {
          result.push({
            service: "Trading Mode",
            status: "healthy",
            uptime: configRes.value.trading_mode?.toUpperCase(),
          });
        } else {
          result.push({ service: "Trading Mode", status: "degraded" });
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
        const user = await apiFetch<any>("/api/auth/me");
        setIsAdmin(user.is_admin === true);
      } catch {
        setIsAdmin(false);
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
