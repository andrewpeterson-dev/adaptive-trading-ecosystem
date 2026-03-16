"use client";

import { Activity, PlugZap, Router } from "lucide-react";
import { StatusChip } from "@/components/ui/status-chip";
import { useTradeStore } from "@/stores/trade-store";

function chipVariantForStatus(status?: string) {
  if (status === "connected") return "positive" as const;
  if (status === "warning") return "warning" as const;
  return "danger" as const;
}

export function TradingConnectionStatus() {
  const status = useTradeStore((state) => state.status);
  const statusLoading = useTradeStore((state) => state.statusLoading);
  const account = useTradeStore((state) => state.account);

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <div className="app-panel flex items-start justify-between gap-3 p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-[18px] border border-border/70 bg-muted/25 p-2.5">
            <Activity className="h-4 w-4 text-primary" />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Market Data
            </p>
            <p className="mt-1 text-sm font-medium text-foreground">
              {statusLoading ? "Checking feed..." : status?.market_data.message || "Feed unavailable"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Source: {status?.market_data.source || "internal quote pipeline"}
            </p>
          </div>
        </div>
        <StatusChip
          variant={chipVariantForStatus(status?.market_data.status)}
          label={status?.market_data.status || "disconnected"}
          icon={<PlugZap className="h-3.5 w-3.5" />}
          pulse={status?.market_data.status === "connected"}
        />
      </div>

      <div className="app-panel flex items-start justify-between gap-3 p-4">
        <div className="flex items-start gap-3">
          <div className="rounded-[18px] border border-border/70 bg-muted/25 p-2.5">
            <Router className="h-4 w-4 text-primary" />
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Order Routing
            </p>
            <p className="mt-1 text-sm font-medium text-foreground">
              {statusLoading ? "Checking router..." : status?.order_routing.message || "Routing unavailable"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Broker: {account?.broker || status?.broker || "not connected"}
            </p>
          </div>
        </div>
        <StatusChip
          variant={chipVariantForStatus(status?.order_routing.status)}
          label={status?.order_routing.status || "disconnected"}
          icon={<PlugZap className="h-3.5 w-3.5" />}
          pulse={status?.order_routing.status === "connected"}
        />
      </div>
    </div>
  );
}
