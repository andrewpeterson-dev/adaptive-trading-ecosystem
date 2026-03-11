"use client";

import { useEffect, useState } from "react";
import { Shield, Loader2, Lock } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { PlatformStats } from "@/components/admin/PlatformStats";
import { UserTable } from "@/components/admin/UserTable";
import type { SystemHealth } from "@/types/admin";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

function normalizeStatus(status?: string): SystemHealth["status"] {
  if (status === "healthy" || status === "up" || status === "ok") return "healthy";
  if (status === "unhealthy" || status === "down" || status === "critical") return "down";
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
      } finally {
        setLoading(false);
      }
    }

    fetchHealth();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="app-panel p-5 sm:p-6">
      <div className="mb-4">
        <h3 className="text-sm font-semibold">System Health</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Service availability and runtime configuration checks.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {services.map((service) => (
          <div key={service.service} className="app-inset p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-sm font-medium">{service.service}</div>
                {service.uptime && (
                  <div className="mt-1 text-xs text-muted-foreground">{service.uptime}</div>
                )}
              </div>
              <Badge
                variant={
                  service.status === "healthy"
                    ? "success"
                    : service.status === "down"
                      ? "danger"
                      : "warning"
                }
              >
                {service.status}
              </Badge>
            </div>
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
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isAdmin === false) {
    return (
      <EmptyState
        icon={<Lock className="h-5 w-5 text-muted-foreground" />}
        title="Access denied"
        description="This area is restricted to administrator accounts. Contact an administrator to request access."
      />
    );
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Operations"
        title="Admin Console"
        description="Inspect platform health, review users, and monitor the operational state of the trading workspace from a single control plane."
        badge={
          <Badge variant="danger">
            <Shield className="h-3.5 w-3.5" />
            Restricted
          </Badge>
        }
      />

      <PlatformStats />
      <UserTable />
      <SystemHealthIndicators />
    </div>
  );
}
