"use client";

import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";
import { Layers } from "lucide-react";
import type { AllocationEntry } from "@/types/portfolio";

const PIE_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"];

function formatCurrency(val: number): string {
  return val.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function AllocationChart({ data }: { data: AllocationEntry[] }) {
  if (data.length === 0) return null;

  const pieData = data.map((a) => ({
    name: a.model_name,
    value: a.weight * 100,
    capital: a.allocated_capital,
  }));

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
        <Layers className="h-4 w-4" />
        Capital Allocation
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={pieData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={95}
            paddingAngle={2}
            label={({ name, value }) => `${name} ${value.toFixed(0)}%`}
          >
            {pieData.map((_, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(222, 47%, 7%)",
              border: "1px solid hsl(222, 47%, 18%)",
              borderRadius: "6px",
              fontSize: "12px",
            }}
            formatter={(val) => [`${Number(val ?? 0).toFixed(1)}%`, "Weight"]}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            formatter={(value: string) => (
              <span className="text-xs text-muted-foreground">{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
