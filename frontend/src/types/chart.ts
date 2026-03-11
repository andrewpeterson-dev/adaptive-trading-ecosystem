export interface CandleData {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface TradeMarker {
  time: string | number;
  price: number;
  side: "buy" | "sell";
  tradeId?: string;
  kind?: "entry" | "exit" | "stop_loss" | "take_profit";
  label?: string;
  text?: string;
  color?: string;
  shape?: "circle" | "square" | "arrowUp" | "arrowDown";
  position?: "aboveBar" | "belowBar" | "inBar";
}

export type TimeFrame = "1m" | "5m" | "15m" | "1H" | "4H" | "1D" | "1W";

export type ChartIndicator =
  | "sma20"
  | "sma50"
  | "ema9"
  | "vwap"
  | "volume"
  | "rsi"
  | "macd";

export interface PriceLevelLine {
  price: number;
  color: string;
  label: string;
  lineStyle?: number; // 0=solid, 1=dotted, 2=dashed
}
