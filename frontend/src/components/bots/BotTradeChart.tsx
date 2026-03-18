"use client";

import type { BotTrade } from "@/lib/cerberus-api";
import { buildTradeMarkers, buildTradePriceLevels } from "@/lib/bot-visualization";
import { TradingChart } from "@/components/charts/TradingChart";
import { TradeMarkerOverlay } from "@/components/bots/TradeMarkerOverlay";

interface BotTradeChartProps {
  symbol: string;
  trades: BotTrade[];
  selectedTrade: BotTrade | null;
  hoveredTrade: BotTrade | null;
  highlightedTradeId: string | null;
  onHoverTrade: (tradeId: string | null) => void;
  onSelectTrade: (tradeId: string | null) => void;
}

export function BotTradeChart({
  symbol,
  trades,
  selectedTrade,
  hoveredTrade,
  highlightedTradeId,
  onHoverTrade,
  onSelectTrade,
}: BotTradeChartProps) {
  const overlayTrade = hoveredTrade ?? selectedTrade;

  return (
    <div className="relative">
      {overlayTrade && (
        <TradeMarkerOverlay trade={overlayTrade} hovered={hoveredTrade != null} />
      )}
      <TradingChart
        symbol={symbol}
        height={420}
        trades={buildTradeMarkers(trades)}
        priceLevels={buildTradePriceLevels(selectedTrade)}
        highlightedTradeId={highlightedTradeId}
        onTradeHover={onHoverTrade}
        onTradeSelect={onSelectTrade}
      />
    </div>
  );
}
