"use client";

import { useCallback, type CSSProperties } from "react";
import { ChevronLeft, ChevronRight, PanelLeft, PanelRight } from "lucide-react";
import { TradingChart } from "@/components/charts/TradingChart";
import { useCerberusStore } from "@/stores/cerberus-store";
import { useTradeStore } from "@/stores/trade-store";
import type { TradeMarker } from "@/types/chart";
import { StockOrderTicket } from "./StockOrderTicket";
import { SymbolSearch } from "./SymbolSearch";
import { SymbolSnapshotCard } from "./SymbolSnapshotCard";
import { TradingConnectionStatus } from "./TradingConnectionStatus";
import { TradingDataTabs } from "./TradingDataTabs";
import { TradingInfoTabs } from "./TradingInfoTabs";
import { TradingWatchlistPanel } from "./TradingWatchlistPanel";
import { TradeAnalysisWidget } from "@/components/trade/TradeAnalysisWidget";

interface TradingWorkspaceProps {
  tradeMarkers: TradeMarker[];
  highlightedTradeId: string | null;
  onRefresh: () => void;
  isPaperMode: boolean;
}

function DrawerShell({
  side,
  title,
  description,
  open,
  onToggle,
  children,
}: {
  side: "left" | "right";
  title: string;
  description: string;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  const isLeft = side === "left";

  if (!open) {
    return (
      <aside className="min-w-0">
        <button
          type="button"
          onClick={onToggle}
          className="app-panel flex min-h-[520px] w-full flex-col items-center justify-center gap-4 px-2 py-5 text-muted-foreground transition-colors hover:text-foreground"
          aria-label={`Expand ${title}`}
        >
          {isLeft ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <PanelRight className="h-4 w-4" />
          )}
          <span className="[writing-mode:vertical-rl] rotate-180 text-[10px] font-semibold uppercase tracking-[0.24em]">
            {title}
          </span>
          <span className="text-[11px] leading-4 text-muted-foreground/80">
            {isLeft ? "Search and watchlist" : "Ticket and info"}
          </span>
        </button>
      </aside>
    );
  }

  return (
    <aside className="min-w-0">
      <div className="app-panel overflow-hidden">
        <div
          className="flex items-start justify-between gap-3 border-b border-border/60 px-4 py-3.5"
        >
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {title}
            </p>
            <p className="mt-1 max-w-[17rem] text-[13px] leading-5 text-muted-foreground">
              {description}
            </p>
          </div>

          <button
            type="button"
            onClick={onToggle}
            className="app-button-icon shrink-0"
            aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
          >
            {isLeft ? (
              open ? <ChevronLeft className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />
            ) : open ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <PanelRight className="h-4 w-4" />
            )}
          </button>
        </div>

        <div className="space-y-4 px-4 py-4">{children}</div>
      </div>
    </aside>
  );
}

export function TradingWorkspace({
  tradeMarkers,
  highlightedTradeId,
  onRefresh,
  isPaperMode,
}: TradingWorkspaceProps) {
  const symbol = useTradeStore((state) => state.symbol);
  const snapshot = useTradeStore((state) => state.snapshot);
  const symbolDetailsLoading = useTradeStore((state) => state.symbolDetailsLoading);
  const watchlist = useTradeStore((state) => state.watchlist);
  const addToWatchlist = useTradeStore((state) => state.addToWatchlist);
  const removeFromWatchlist = useTradeStore((state) => state.removeFromWatchlist);
  const leftDrawerOpen = useTradeStore((state) => state.leftDrawerOpen);
  const rightDrawerOpen = useTradeStore((state) => state.rightDrawerOpen);
  const setHighlightedTradeId = useTradeStore((state) => state.setHighlightedTradeId);
  const toggleLeftDrawer = useTradeStore((state) => state.toggleLeftDrawer);
  const toggleRightDrawer = useTradeStore((state) => state.toggleRightDrawer);
  const openCerberus = useCerberusStore((state) => state.openCerberus);
  const setActiveTab = useCerberusStore((state) => state.setActiveTab);

  const gridTemplateColumns =
    leftDrawerOpen && rightDrawerOpen
      ? "280px minmax(0,1fr) 380px"
      : leftDrawerOpen && !rightDrawerOpen
        ? "280px minmax(0,1fr) 76px"
        : !leftDrawerOpen && rightDrawerOpen
          ? "76px minmax(0,1fr) 380px"
          : "76px minmax(0,1fr) 76px";

  const layoutStyle: CSSProperties = {
    ["--trade-layout" as string]: gridTemplateColumns,
  };

  const watched = watchlist.includes(symbol.toUpperCase());
  const openResearch = useCallback(() => {
    setActiveTab("research");
    openCerberus();
  }, [openCerberus, setActiveTab]);

  return (
    <div className="space-y-4">
      <TradingConnectionStatus />

      <div className="space-y-4 xl:hidden">
        <div className="app-panel p-4 sm:p-5">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Symbols
          </p>
          <SymbolSearch />
        </div>
        <SymbolSnapshotCard
          snapshot={snapshot}
          loading={symbolDetailsLoading}
          isWatched={watched}
          onToggleWatchlist={() => {
            if (watched) {
              removeFromWatchlist(symbol);
            } else {
              addToWatchlist(symbol);
            }
          }}
          onOpenResearch={openResearch}
        />
        <TradingWatchlistPanel />
        <TradingChart
          symbol={symbol}
          trades={tradeMarkers}
          highlightedTradeId={highlightedTradeId}
          onTradeSelect={setHighlightedTradeId}
        />
        <StockOrderTicket onOrderPlaced={onRefresh} isPaperMode={isPaperMode} />
        <TradeAnalysisWidget />
        <TradingInfoTabs />
        <TradingDataTabs onRefresh={onRefresh} />
      </div>

      <div className="hidden gap-4 xl:grid xl:[grid-template-columns:var(--trade-layout)]" style={layoutStyle}>
        <DrawerShell
          side="left"
          title="Symbols"
          description="Search, inspect, and keep your active watchlist close to the chart."
          open={leftDrawerOpen}
          onToggle={toggleLeftDrawer}
        >
          <SymbolSearch />
          <SymbolSnapshotCard
            snapshot={snapshot}
            loading={symbolDetailsLoading}
            isWatched={watched}
            onToggleWatchlist={() => {
              if (watched) {
                removeFromWatchlist(symbol);
              } else {
                addToWatchlist(symbol);
              }
            }}
            onOpenResearch={openResearch}
          />
          <TradingWatchlistPanel />
        </DrawerShell>

        <div className="min-w-0 space-y-4">
          <div className="min-h-[400px]">
            <TradingChart
              symbol={symbol}
              trades={tradeMarkers}
              highlightedTradeId={highlightedTradeId}
              onTradeSelect={setHighlightedTradeId}
            />
          </div>
          <TradingDataTabs onRefresh={onRefresh} />
        </div>

        <DrawerShell
          side="right"
          title="Execution"
          description="Stage orders, review buying-power impact, and inspect symbol intelligence."
          open={rightDrawerOpen}
          onToggle={toggleRightDrawer}
        >
          <StockOrderTicket onOrderPlaced={onRefresh} isPaperMode={isPaperMode} />
          <TradeAnalysisWidget />
          <TradingInfoTabs />
        </DrawerShell>
      </div>
    </div>
  );
}
