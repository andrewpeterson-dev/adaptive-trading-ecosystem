"use client";

import { Activity, ArrowLeftRight, DatabaseZap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useTradeStore } from "@/stores/trade-store";

const STATUS_VARIANT = {
  connected: "success",
  warning: "warning",
  disconnected: "danger",
} as const;

export function ConnectionStatusBar() {
  const status = useTradeStore((state) => state.status);
  const account = useTradeStore((state) => state.account);

  if (!status) {
    return (
      <div className="app-panel flex flex-wrap items-center gap-2 px-4 py-3">
        <Badge variant="neutral">Checking market data</Badge>
        <Badge variant="neutral">Checking order routing</Badge>
      </div>
    );
  }

  return (
    <div className="app-panel flex flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="neutral">
          <DatabaseZap className="h-3.5 w-3.5" />
          {status.mode.toUpperCase()}
        </Badge>
        <Badge variant={STATUS_VARIANT[status.market_data.status]}>
          <Activity className="h-3.5 w-3.5" />
          Market data {status.market_data.status}
        </Badge>
        <Badge variant={STATUS_VARIANT[status.order_routing.status]}>
          <ArrowLeftRight className="h-3.5 w-3.5" />
          Order routing {status.order_routing.status}
        </Badge>
      </div>

      <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2 lg:min-w-[520px]">
        <div className="rounded-2xl border border-border/60 bg-muted/30 px-3 py-2">
          <span className="font-semibold text-foreground">Market data</span>
          <span className="ml-2">{status.market_data.message}</span>
        </div>
        <div className="rounded-2xl border border-border/60 bg-muted/30 px-3 py-2">
          <span className="font-semibold text-foreground">Routing</span>
          <span className="ml-2">
            {status.order_routing.message}
            {account?.buying_power != null ? ` · ${account.buying_power.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })} BP` : ''}
          </span>
        </div>
      </div>
    </div>
  );
}
