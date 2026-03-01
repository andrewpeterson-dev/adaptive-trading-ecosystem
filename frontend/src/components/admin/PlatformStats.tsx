"use client";

import {
  Users,
  UserCheck,
  BarChart3,
  Brain,
  Activity,
  Loader2,
} from "lucide-react";
import { useEffect, useState, useCallback } from "react";

interface StatCard {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  description?: string;
}

export function PlatformStats() {
  const [stats, setStats] = useState<StatCard[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    try {
      const [usersRes, modelsRes, configRes] = await Promise.allSettled([
        fetch("/api/admin/users"),
        fetch("/api/models/list"),
        fetch("/api/system/config"),
      ]);

      const cards: StatCard[] = [];

      if (usersRes.status === "fulfilled" && usersRes.value.ok) {
        const users = await usersRes.value.json();
        const userList = Array.isArray(users) ? users : users.users || [];
        cards.push({
          label: "Total Users",
          value: userList.length,
          icon: <Users className="h-5 w-5 text-blue-400" />,
        });
        cards.push({
          label: "Verified Users",
          value: userList.filter((u: any) => u.email_verified).length,
          icon: <UserCheck className="h-5 w-5 text-emerald-400" />,
        });
        cards.push({
          label: "Admin Users",
          value: userList.filter((u: any) => u.is_admin).length,
          icon: <Activity className="h-5 w-5 text-purple-400" />,
        });
      } else {
        cards.push(
          { label: "Total Users", value: "--", icon: <Users className="h-5 w-5 text-blue-400" /> },
          { label: "Verified Users", value: "--", icon: <UserCheck className="h-5 w-5 text-emerald-400" /> },
          { label: "Admin Users", value: "--", icon: <Activity className="h-5 w-5 text-purple-400" /> },
        );
      }

      if (modelsRes.status === "fulfilled" && modelsRes.value.ok) {
        const models = await modelsRes.value.json();
        const modelList = Array.isArray(models) ? models : [];
        cards.push({
          label: "Active Models",
          value: modelList.length,
          icon: <Brain className="h-5 w-5 text-amber-400" />,
        });
      } else {
        cards.push({
          label: "Active Models",
          value: "--",
          icon: <Brain className="h-5 w-5 text-amber-400" />,
        });
      }

      if (configRes.status === "fulfilled" && configRes.value.ok) {
        const config = await configRes.value.json();
        cards.push({
          label: "Trading Mode",
          value: config.trading_mode?.toUpperCase() || "--",
          icon: <BarChart3 className="h-5 w-5 text-cyan-400" />,
          description: `Max ${config.max_trades_per_hour} trades/hr`,
        });
      } else {
        cards.push({
          label: "Trading Mode",
          value: "--",
          icon: <BarChart3 className="h-5 w-5 text-cyan-400" />,
        });
      }

      setStats(cards);
    } catch {
      // Keep empty stats on error
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="rounded-lg border border-border/50 bg-card p-4 space-y-2"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground uppercase tracking-wider">
              {stat.label}
            </span>
            {stat.icon}
          </div>
          <div className="text-2xl font-bold font-mono tabular-nums">{stat.value}</div>
          {stat.description && (
            <p className="text-xs text-muted-foreground">{stat.description}</p>
          )}
        </div>
      ))}
    </div>
  );
}
