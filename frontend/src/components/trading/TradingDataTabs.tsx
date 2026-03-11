"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OpenOrdersPanel } from "./OpenOrdersPanel";
import { PositionsPanel } from "./PositionsPanel";
import { TradeHistoryPanel } from "./TradeHistoryPanel";

interface TradingDataTabsProps {
  onRefresh: () => void;
}

export function TradingDataTabs({ onRefresh }: TradingDataTabsProps) {
  return (
    <Tabs defaultValue="positions">
      <div className="app-panel p-4 sm:p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Execution Panels
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              Positions, working orders, and completed executions live here.
            </p>
          </div>
          <TabsList>
            <TabsTrigger value="positions">Positions</TabsTrigger>
            <TabsTrigger value="orders">Open Orders</TabsTrigger>
            <TabsTrigger value="history">Trade History</TabsTrigger>
          </TabsList>
        </div>
      </div>

      <TabsContent value="positions" className="mt-4">
        <PositionsPanel onClose={onRefresh} />
      </TabsContent>

      <TabsContent value="orders" className="mt-4">
        <OpenOrdersPanel />
      </TabsContent>

      <TabsContent value="history" className="mt-4">
        <TradeHistoryPanel />
      </TabsContent>
    </Tabs>
  );
}
